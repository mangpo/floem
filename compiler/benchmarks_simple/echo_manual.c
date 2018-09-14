// gcc -O3 -msse4.1 -D_LARGEFILE64_SOURCE=1 -I /sampa/home/mangpo/flexnic-language-mockup/compiler/include -I /opt/dpdk//include/dpdk -L /opt/dpdk//lib/ echo_manual.c  -o echo_manual -Wl,--whole-archive -lrte_pmd_ixgbe -lrte_pmd_i40e -lrte_eal -lrte_mempool -lrte_mempool_ring -lrte_hash -lrte_ring -lrte_kvargs -lrte_ethdev -lrte_mbuf -lrte_pmd_ring -Wl,--no-whole-archive -lm -lpthread -ldl -lm -pthread -lrt -std=gnu99

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>

#include <rte_eal.h>
#include <rte_errno.h>
#include <rte_launch.h>
#include <rte_memcpy.h>
#include <rte_lcore.h>

/* Enable key-based steering if DPDK is enabled */
#ifndef DPDK_IPV6
#define DPDK_IPV6 0
#endif

/* DPDK batch size */
#ifndef BATCH_MAX
#define BATCH_MAX 32
#endif

#define DPDK_V4_HWXSUM 1
#define MAX_MSGSIZE 2048


#include <rte_ether.h>
#include <rte_ip.h>
#include <rte_udp.h>
#include <rte_arp.h>
#include <rte_ethdev.h>

#include "protocol_binary2.h"

struct iokvs_message {
    struct ether_hdr ether;
#if DPDK_IPV6
    struct ipv6_hdr ipv6;
#else
    struct ipv4_hdr ipv4;
#endif
    struct udp_hdr udp;
    memcached_udp_header mcudp;
    protocol_binary_request_header mcr;
    uint8_t payload[];
} __attribute__ ((packed));

static const struct rte_eth_conf eth_config = {
    .rxmode = {
        .mq_mode = ETH_MQ_RX_RSS,
        .hw_ip_checksum = 1,
        .hw_strip_crc = 1,
    },
    .txmode = {
        .mq_mode = ETH_MQ_TX_NONE,
    },
    .rx_adv_conf = {
        .rss_conf = {
#if DPDK_IPV6
            .rss_hf = ETH_RSS_IPV6,
#else
            .rss_hf = ETH_RSS_NONFRAG_IPV4_UDP,
#endif
        },
    },
    .fdir_conf = {
        .mode = RTE_FDIR_MODE_NONE,
    },
};

static const struct rte_eth_txconf eth_txconf = {
    .txq_flags = ETH_TXQ_FLAGS_NOOFFLOADS,
};

static struct rte_mempool *mempool;
static struct ether_addr mymac;
static unsigned num_ports;

static void network_init(void)
{
    int res, i, q, n = rte_lcore_count();
    unsigned j;

    mempool = rte_mempool_create("bufpool", 16 * 1024,
             MAX_MSGSIZE + sizeof(struct rte_mbuf) + RTE_PKTMBUF_HEADROOM, 32,
             sizeof(struct rte_pktmbuf_pool_private), rte_pktmbuf_pool_init,
             NULL, rte_pktmbuf_init, NULL, rte_socket_id(), 0);

    num_ports = rte_eth_dev_count();
    if (num_ports == 0) {
        fprintf(stderr, "No network cards detected\n");
        abort();
    }
    for (j = 0; j < num_ports; j++) {
        if (rte_eth_dev_configure(j, n , n, &eth_config) != 0) {
            fprintf(stderr, "rte_eth_dev_configure failed\n");
            abort();
        }

        if (j == 0) {
            rte_eth_macaddr_get(0, &mymac);
        }
        rte_eth_promiscuous_enable(j);

        printf("Preparing queues... %u", j);
        q = 0;
        RTE_LCORE_FOREACH(i) {
            if ((res = rte_eth_rx_queue_setup(j, q, 512, rte_lcore_to_socket_id(i),
                            NULL, mempool)) < 0)
            {
                fprintf(stderr, "rte_eth_rx_queue_setup failed: %d %s\n", res,
                        strerror(-res));
                abort();
            }

            if ((res = rte_eth_tx_queue_setup(j, q, 512, rte_lcore_to_socket_id(i),
                            &eth_txconf)) < 0)
            {
                fprintf(stderr, "rte_eth_tx_queue_setup failed: %d %s\n", res,
                        strerror(-res));
                abort();
            }
            printf("Done with queue %u %d\n", j, q);
            q++;
        }

        printf("Starting device %u\n", j);
        rte_eth_dev_start(j);
        printf("Device started %u\n", j);
    }
}

static size_t packet_loop(unsigned p, uint16_t q)
{
    struct rte_mbuf *mbufs[BATCH_MAX];

    struct iokvs_message *m;
    int i, n;

    if ((n = rte_eth_rx_burst(p, q, mbufs, BATCH_MAX)) <= 0) {
        return 0;
    }
    //printf("got %d packets[q=%u]\n", n, q);

    for (i = 0; i < n; i++) {
        m = rte_pktmbuf_mtod(mbufs[i], struct iokvs_message *);

        struct ether_addr src = m->ether.s_addr;
        struct ether_addr dest = m->ether.d_addr;
        m->ether.s_addr = dest;
        m->ether.d_addr = src;

        uint32_t src_ip = m->ipv4.src_addr;
        uint32_t dest_ip = m->ipv4.dst_addr;
        m->ipv4.src_addr = dest_ip;
        m->ipv4.dst_addr = src_ip;

        uint16_t src_port = m->udp.src_port;
        uint16_t dest_port = m->udp.dst_port;
        m->udp.dst_port = src_port;
        m->udp.src_port = dest_port;

        m->mcr.request.magic = PROTOCOL_BINARY_RES;
        m->mcr.request.opcode = PROTOCOL_BINARY_CMD_GET;
        m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
        m->mcr.request.status = htons(PROTOCOL_BINARY_RESPONSE_KEY_ENOENT);
    }

    i = rte_eth_tx_burst(p, q, mbufs, n);
    for (; i < n; i++) {
        rte_pktmbuf_free(mbufs[i]);
    }

    return n;
}

static size_t n_ready = 0;

static int processing_thread(void *data)
{
    unsigned p;
    static uint16_t qcounter;
    uint16_t q;

    q = __sync_fetch_and_add(&qcounter, 1);
    p = 0;

    __sync_fetch_and_add(&n_ready, 1);

    printf("Worker starting\n");

    while (1) {
        packet_loop(p, q);
        p = (p + 1) % num_ports;
    }

    return 0;
}

int main(int argc, char *argv[])
{
    int n;
    if ((n = rte_eal_init(argc, argv)) < 0) {
        fprintf(stderr, "rte_eal_init failed: %s\n", rte_strerror(rte_errno));
        return -1;
    }

    argc -= n;
    argv += n;

    printf("Initailizing networking\n");
    network_init();
    printf("Networking initialized\n");

    rte_eal_mp_remote_launch(processing_thread, NULL, CALL_MASTER);
    return 0;
}
