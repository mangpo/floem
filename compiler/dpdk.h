#ifndef DPDK_H_
#define DPDK_H_

#include <stdint.h>
#include <stddef.h>
#include <stdio.h>

#include <rte_config.h>
#include <rte_memcpy.h>
#include <rte_malloc.h>
#include <rte_lcore.h>
#include <rte_ether.h>
#include <rte_ethdev.h>
#include <rte_mempool.h>
#include <rte_mbuf.h>

/* these are non-static on purpose! */
uint8_t dpdk_port_id;
uint8_t dpdk_thread_num;
uint8_t dpdk_rx_num;
uint64_t dpdk_mac_addr;
struct rte_mempool *dpdk_pool;

static void dpdk_init(char *argv[], unsigned num_threads,
        unsigned num_rx)
{
    struct rte_eth_conf port_conf;
    struct rte_eth_dev_info dev_info;
    int n, ret;
    uint16_t q;
    int argc;

    dpdk_port_id = 0;
    dpdk_thread_num = num_threads;
    dpdk_rx_num = num_rx;

    for (argc = 0; argv[argc] != NULL; argc++);

    /* initialize dpdk runtime */
    if ((n = rte_eal_init(argc, argv)) < 0) {
        fprintf(stderr, "dpdk_init: rte_eal_init failed\n");
        abort();
    }

    if (rte_eth_dev_count() != 1) {
        fprintf(stderr, "dpdk_init: rte_eth_dev_count must be exactly 1\n");
        abort();
    }
    if (num_threads >= rte_lcore_count()) {
        fprintf(stderr, "dpdk_init: more threads than there are cores\n");
        abort();
    }

    /* initialize pool */
    dpdk_pool = rte_mempool_create("dpdk_pool", 8192,
            (2048 + sizeof(struct rte_mbuf) + RTE_PKTMBUF_HEADROOM), 32,
            sizeof(struct rte_pktmbuf_pool_private), rte_pktmbuf_pool_init, NULL,
            rte_pktmbuf_init, NULL, rte_socket_id(), 0);
    if (dpdk_pool == NULL) {
        fprintf(stderr, "dpdk_init: buffer pool init failed\n");
        abort();
    }

    /* configure device */
    memset(&port_conf, 0, sizeof(port_conf));
    port_conf.rxmode.mq_mode = ETH_MQ_RX_RSS;
    port_conf.txmode.mq_mode = ETH_MQ_TX_NONE;
    port_conf.rx_adv_conf.rss_conf.rss_hf= ETH_RSS_TCP;
    ret = rte_eth_dev_configure(dpdk_port_id, num_rx, num_threads, &port_conf);
    if (ret < 0) {
        fprintf(stderr, "dpdk_init: rte_eth_dev_configure failed\n");
        abort();
    }

    /* get mac address and device information */
    dpdk_mac_addr = 0;
    rte_eth_macaddr_get(dpdk_port_id, (struct ether_addr *) &dpdk_mac_addr);
    rte_eth_dev_info_get(dpdk_port_id, &dev_info);

    /* initialize send queues */
    for (q = 0; q < num_threads; q++) {
        ret = rte_eth_tx_queue_setup(dpdk_port_id, q, 256,
                rte_socket_id(), &dev_info.default_txconf);
        if (ret != 0) {
            fprintf(stderr, "dpdk_init: configuring tx queue %u failed\n", q);
            abort();
        }
    }

    /* initialize receive queues */
    for (q = 0; q < num_rx; q++) {
        ret = rte_eth_rx_queue_setup(dpdk_port_id, q, 128, rte_socket_id(),
                &dev_info.default_rxconf, dpdk_pool);
        if (ret != 0) {
            fprintf(stderr, "dpdk_init: configuring rx queue %u failed\n", q);
            abort();
        }
    }

    /* start device */
    if (rte_eth_dev_start(dpdk_port_id) != 0) {
        fprintf(stderr, "dpdk_init: rte_eth_dev_start failed\n");
        abort();
    }
}

static void dpdk_thread_create(void *(*entry_point)(void *), void *arg)
{
    static volatile uint8_t thread_id = 0;
    uint8_t id = __sync_fetch_and_add(&thread_id, 1);
    int ret;

    if (id >= dpdk_thread_num) {
        fprintf(stderr, "dpdk_thread_create: specified number of threads "
                "exceeded\n");
        abort();
    }

    ret = rte_eal_remote_launch((void *) entry_point, arg, id + 1);
    if (ret != 0) {
        fprintf(stderr, "dpdk_thread_create: rte_eal_remote_launch failed\n");
        abort();
    }
}

static void dpdk_from_net(void **pdata, void **pbuf)
{
    static volatile uint16_t rx_queue_alloc = 0;
    static __thread uint16_t rx_queue_id;
    struct rte_mbuf *mb = NULL;
    void *data = NULL;

    /* get queue ID/initialize queue */
    uint16_t rxq = rx_queue_id;
    if (rxq == 0) {
        rxq = __sync_fetch_and_add(&rx_queue_alloc, 1);

        if (rxq >= dpdk_rx_num) {
            fprintf(stderr, "dpdk_from_net: too many rx queues\n");
            abort();
        }
        rxq++;
        rx_queue_id = rxq;
    }
    rxq--;

    unsigned num = rte_eth_rx_burst(dpdk_port_id, rxq, &mb, 1);
    if (num >= 1)
        data = (uint8_t *) mb->buf_addr + mb->data_off;

    *pdata = data;
    *pbuf = mb;
}

static void dpdk_net_free(void *data, void *buf)
{
    rte_pktmbuf_free(buf);
}

static void dpdk_net_alloc(size_t len, void **pdata, void **pbuf)
{
    void *data = NULL;
    struct rte_mbuf *mb = rte_pktmbuf_alloc(dpdk_pool);

    if (mb != NULL)
        data = (uint8_t *) mb->buf_addr + 128;

    *pdata = data;
    *pbuf = mb;
}

static void dpdk_to_net(size_t size, void *data, void *buf)
{
    static volatile uint16_t tx_queue_alloc = 0;
    static __thread uint16_t tx_queue_id;
    struct rte_mbuf *mb = buf;
    mb->pkt_len = mb->data_len = size;
    mb->data_off = (uint8_t *) data - (uint8_t *) mb->buf_addr;

    /* get queue ID/initialize queue */
    uint16_t txq = tx_queue_id;
    if (txq == 0) {
        txq = __sync_fetch_and_add(&tx_queue_alloc, 1);

        if (txq >= dpdk_thread_num) {
            fprintf(stderr, "dpdk_to_net: too many tx queues\n");
            abort();
        }
        txq++;
        tx_queue_id = txq;
    }
    txq--;

    if (rte_eth_tx_burst(dpdk_port_id, txq, &mb, 1) != 1) {
        rte_pktmbuf_free(mb);
    }
}

#endif /* ndef DPDK_H_ */
