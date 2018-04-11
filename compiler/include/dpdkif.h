#ifndef DPDK_H_
#define DPDK_H_

#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <sys/time.h>

#include <rte_config.h>
#include <rte_memcpy.h>
#include <rte_malloc.h>
#include <rte_lcore.h>
#include <rte_ether.h>
#include <rte_ethdev.h>
#include <rte_mempool.h>
#include <rte_mbuf.h>

typedef rte_spinlock_t spinlock_t;

#define spinlock_init(x) rte_spinlock_init(x)
#define spinlock_lock(x) rte_spinlock_lock(x)
#define spinlock_unlock(x) rte_spinlock_unlock(x)

#define __sync_fetch_and_add32(ptr, inc) __sync_fetch_and_add(ptr, inc)
#define __sync_fetch_and_add64(ptr, inc) __sync_fetch_and_add(ptr, inc)
#define __sync_bool_compare_and_swap32(ptr, old, new) __sync_bool_compare_and_swap(ptr, old, new)
#define __sync_bool_compare_and_swap64(ptr, old, new) __sync_bool_compare_and_swap(ptr, old, new)

#define shared_mm_malloc(size) malloc(size)
#define shared_mm_free(p) free(p)

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
    port_conf.rx_adv_conf.rss_conf.rss_hf= ETH_RSS_TCP | ETH_RSS_UDP;
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
                "exceeded. (id = %d >= dpdk_thread_num = %d)\n", id, dpdk_thread_num);
        abort();
    }

    ret = rte_eal_remote_launch((void *) entry_point, arg, id + 1);
    if (ret != 0) {
        fprintf(stderr, "dpdk_thread_create: rte_eal_remote_launch failed\n");
        abort();
    }
}

#define BATCH_SIZE_MAX 1024
static void dpdk_from_net(size_t *sz, void **pdata, void **pbuf, int BATCH_SIZE_IN)
{
    static volatile uint16_t rx_queue_alloc = 0;
    static __thread uint32_t rx_queue_id = 0;
    struct rte_mbuf *mb = NULL;
    static __thread unsigned cache_count;
    static __thread unsigned cache_index;
    static __thread struct rte_mbuf *cache_mbs[BATCH_SIZE_MAX];
    struct rte_mbuf **mbs;
    void *data = NULL;
    unsigned num, idx;

    /* check cache first */
    mbs = cache_mbs;
    num = cache_count;
    if (num > 0) {
      idx = cache_index;
      mb = mbs[idx];
      if (++idx >= num) {
        cache_count = 0;
      }
      cache_index = idx;
      goto out;
    }

    /* get queue ID/initialize queue */
    uint32_t rxq = rx_queue_id;
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

    /* get more packets from NIC */
    num = rte_eth_rx_burst(dpdk_port_id, rxq, mbs, BATCH_SIZE_IN);
    mb = mbs[0];
    if (num > 1) {
      cache_count = num;
      cache_index = 1;
    }

out:
    if (num >= 1) {
        data = (uint8_t *) mb->buf_addr + mb->data_off;
        *sz = mb->data_len;
    }

    *pdata = data;
    *pbuf = mb;
    
#if 0
    static __thread size_t count = 0;
    static __thread struct timeval last, now;

    if(data) {
      gettimeofday(&now, NULL);
      count++;
      //if(now.tv_sec > last.tv_sec) {
      //printf("rx_queue_id = %d\n", rx_queue_id);
	printf("from_net[%d]: %ld pkts/s\n", rxq, count);
	//count = 0;
	//last = now;
	//}
      /*
      printf("from_net: size = %ld\n", *sz);
      int i;
      uint8_t* x = (uint8_t*) data;
      for(i=0; i<*sz; i++) {
	if(i%16==0) printf("\n");
	printf("%x ", x[i]);
      }
      printf("\n\n");
      */
    }
#endif
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

static void dpdk_to_net(size_t size, void *data, void *buf, int BATCH_SIZE_OUT)
{
    static volatile uint16_t tx_queue_alloc = 0;
    static __thread uint16_t tx_queue_id, n = 0;
    static __thread int batch_size = 0;
    if(batch_size == 0) batch_size = BATCH_SIZE_OUT;
  
  int j;
  uint8_t* x = (uint8_t*) data;
  
    static __thread struct rte_mbuf *mbufs[BATCH_SIZE_MAX];
    struct rte_mbuf *mb = buf;
    mb->pkt_len = mb->data_len = size;
    mb->data_off = (uint8_t *) data - (uint8_t *) mb->buf_addr;
    mbufs[n] = mb;
    n++;

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

#if 0
    printf("to_net: size = %ld, n = %d/%d, txq = %d\n", size, n, batch_size, txq);
    //uint16_t* task =  (uint16_t*) (x + 46);
    //printf("task: task = %d\n", *task);
    for(j=0; j<size; j++) {
      if(j%16==0) printf("\n");
      printf("%x ", x[j]);
    }
    printf("\n\n");
#endif

    uint16_t i = 0, inc;
    if(n >= batch_size) {
      while (i < n) {
        inc = rte_eth_tx_burst(dpdk_port_id, txq, mbufs + i, n - i);
        i += inc;
      }
      n = 0;
    }

    static __thread size_t count = 0;
    static __thread struct timeval last, now;

    gettimeofday(&now, NULL);
    count++;
    if(now.tv_sec > last.tv_sec) {
      batch_size = (count > 1000)? BATCH_SIZE_OUT: 1;
#if 0
      printf("to_net[%d]: %ld pkts/s, batch_size = %d\n", txq, count, batch_size);
#endif
      count = 0;
      last = now;
    }

}

#endif /* ndef DPDK_H_ */
