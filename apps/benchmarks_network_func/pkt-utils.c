/*
 * Packet utilities implementation
 */
#include <string.h>
#include "pkt-utils.h"
#include "cluster-setup.h"

#ifdef CAVIUM
#include "cvmx-config.h"
#include "cvmx.h"
#include "cvmx-pko.h"
#else
#include <stdio.h>
#endif


#define POLY 0x8408
/*
 *                                     16   12   5
 * This is the CCITT CRC 16 polynomial X  + X  + X  + 1.
 * This works out to be 0x1021, but the way the algorithm works
 * lets us use 0x8408 (the reverse of the bit pattern).  The high
 * bit is always assumed to be set, thus we only use 16 bits to
 * represent the 17 bit value.
 */
static uint32_t
crc16(uint8_t *data_p,
      uint16_t length)
{
    uint8_t i;
    uint32_t data, crc = 0xffff;

    if (length == 0)
        return (~crc);

    do {
        for (i=0, data=(unsigned int)0xff & *data_p++; i < 8; i++, data >>= 1) {
            if ((crc & 0x0001) ^ (data & 0x0001)) {
                crc = (crc >> 1) ^ POLY;
            } else {
                crc >>= 1;
            }
        }
    } while (--length);

    crc = ~crc;
    data = crc;
    crc = (crc << 8) | (data >> 8 & 0xff);

    return (crc);
}

#define FIVE_TUPLE_LEN 13
#define ETHER_DES_POS 0
#define ETHER_SRC_POS 6
#define ETHER_HEADER_LEN 14
#define IP_PROTOCOL_POS 23
#define IP_CHKSUM_POS 24
#define IP_SRC_POS 26
#define IP_DES_POS 30
#define IP_HEADER_LEN 20
#define UDP_SRC_POS 34
#define UDP_DES_POS 36
#define UDP_PAYLOAD 42
#define TCP_SRC_POS 34
#define TCP_DES_POS 36
#define UDP_CHKSUM_POS 40
#define UDP_HEADER_LEN 8
#define TCP_HEADER_LEN 20
#define PAYLOAD_SIZE 1500
#define TCP_PSEUDO_START 22
#define PSEUDO_TCP_HEADER_LEN 12
#define TCP_CHKSUM_POS 50
#define UDP 17
#define TCP 6

bool
pkt_filter(uint8_t *pkt_ptr)
{
  /* int i; */
  /* for(i=0; i<32;i++) */
  /*   printf("%x ", pkt_ptr[i]); */
  /* printf("\n"); */
  /* printf("UDP: pkt[%d] = %d %d\n", IP_PROTOCOL_POS, pkt_ptr[IP_PROTOCOL_POS], 0x11); */
    // UDP only
    if (pkt_ptr[IP_PROTOCOL_POS] == 0x11) {
        return false;
    }

    return true;
}

uint32_t
get_flow_id(uint8_t *pkt_ptr)
{
    uint8_t five_tuple[FIVE_TUPLE_LEN], pos = 0, protocol;

    protocol = pkt_ptr[IP_PROTOCOL_POS];
    memcpy(five_tuple + pos, pkt_ptr + IP_PROTOCOL_POS, 1);
    pos += 1;

    if (protocol == UDP) {
        memcpy(five_tuple + pos, pkt_ptr + IP_SRC_POS, 4);
        pos += 4;
        memcpy(five_tuple + pos, pkt_ptr + IP_DES_POS, 4);
        pos += 4;
        memcpy(five_tuple + pos, pkt_ptr + UDP_SRC_POS, 2);
        pos += 2;
        memcpy(five_tuple + pos, pkt_ptr + UDP_DES_POS, 2);
        pos += 2;
    }

    if (protocol == TCP) {
        memcpy(five_tuple + pos, pkt_ptr + IP_SRC_POS, 4);
        pos += 4;
        memcpy(five_tuple + pos, pkt_ptr + IP_DES_POS, 4);
        pos += 4;
        memcpy(five_tuple + pos, pkt_ptr + TCP_SRC_POS, 2);
        pos += 2;
        memcpy(five_tuple + pos, pkt_ptr + TCP_DES_POS, 2);
        pos += 2;
    }

    return crc16(pkt_ptr, FIVE_TUPLE_LEN);
}

/* in_chksum
 * brief Checksum routine for Internet Protocol family headers
 * param[in] addr a pointer to the data
 * param[in] len the 32 bits data size
 * return sum a 16 bits checksum
 */
static uint16_t
in_chksum(uint16_t *addr,
          int len)
{
    int sum = 0;
    uint16_t answer = 0;
    uint16_t *w = addr;
    int nleft = len;

    /*
     * Our algorithm is simple, using a 32 bit accumulator (sum), we add
     * sequential 16 bit words to it, and at the end, fold back all the
     * carry bits from the top 16 bits into the lower 16 bits.
     */
    while (nleft > 1) {
        sum += *w++;
        nleft -= 2;
    }

    /*! mop up an odd byte, if necessary */
    if (nleft == 1) {
        *(uint8_t *)(&answer) = *(uint8_t *)w;
        sum += answer;
    }

    /*! add back carry outs from top 16 bits to low 16 bits */
    sum = (sum >> 16) + (sum & 0xffff);     /*! add hi 16 to low 16 */
    sum += (sum >> 16);                     /*! add carry */
    answer = ~sum;                          /*! truncate to 16 bits */
    return answer;
}

static void
swap_ether_header(uint8_t *pkt_ptr)
{
    uint8_t tmp[MAC_ADDRESS_LEN];

    memcpy(tmp, pkt_ptr + ETHER_SRC_POS, MAC_ADDRESS_LEN);

    // source mac
    memcpy(pkt_ptr + ETHER_SRC_POS,
           pkt_ptr + ETHER_DES_POS,
           MAC_ADDRESS_LEN);

    // destination mac
    memcpy(pkt_ptr + ETHER_DES_POS,
           tmp,
           MAC_ADDRESS_LEN);
}

static void
swap_ip_header(uint8_t *pkt_ptr)
{
    uint8_t tmp[IP_ADDRESS_LEN];

    memcpy(tmp, pkt_ptr + IP_SRC_POS, IP_ADDRESS_LEN);

    // source ip
    memcpy(pkt_ptr + IP_SRC_POS,
           pkt_ptr + IP_DES_POS,
           IP_ADDRESS_LEN);

    // destination ip
    memcpy(pkt_ptr + IP_DES_POS,
           tmp,
           IP_ADDRESS_LEN);
}

static void
swap_udp_header(uint8_t *pkt_ptr)
{
    uint8_t tmp[2];

    memcpy(tmp, pkt_ptr + UDP_SRC_POS, 2);

    // source udp port
    memcpy(pkt_ptr + UDP_SRC_POS,
           pkt_ptr + UDP_DES_POS,
           2);

    // destination udp port
    memcpy(pkt_ptr + UDP_DES_POS,
           tmp,
           2);
}

static void
recalculate_ip_chksum(uint8_t *pkt_ptr)
{
    *(uint16_t *)(pkt_ptr + IP_CHKSUM_POS) = 0x0000;
    *(uint16_t *)(pkt_ptr + IP_CHKSUM_POS) = in_chksum((uint16_t *)(pkt_ptr +
                                                       ETHER_HEADER_LEN),
                                                       IP_HEADER_LEN); // TODO: on cpu?
}

static void
recalculate_udp_chksum(uint8_t *pkt_ptr)
{
    *(uint16_t *)(pkt_ptr + UDP_CHKSUM_POS) = 0x0000;
}

struct tcphdr {
    uint16_t th_sport;       /* source port */
    uint16_t th_dport;       /* destination port */
    uint32_t th_seq;         /* sequence number */
    uint32_t th_ack;         /* acknowledgement number */
#if BYTE_ORDER == LITTLE_ENDIAN
    uint8_t  th_x2:4,        /* (unused) */
             th_off:4;       /* data offset */
#endif
#if BYTE_ORDER == BIG_ENDIAN
    uint8_t  th_off:4,       /* data offset */
             th_x2:4;        /* (unused) */
#endif
    uint8_t  th_flags;
#define TH_FIN  0x01
#define TH_SYN  0x02
#define TH_RST  0x04
#define TH_PUSH 0x08
#define TH_ACK  0x10
#define TH_URG  0x20
    uint16_t th_win;         /* window */
    uint16_t th_sum;         /* checksum */
    uint16_t th_urp;         /* urgent pointer */
};


typedef struct _tcp_pseudo_hdr {
    uint8_t src_addr[IP_ADDRESS_LEN];
    uint8_t des_addr[IP_ADDRESS_LEN];
    uint8_t reserved;
    uint8_t protocol;
    uint16_t len;
    struct tcphdr tcp_hdr;
    uint8_t payload[PAYLOAD_SIZE];
} tcp_pseudo_hdr;

static bool
is_echo_pkt(uint8_t *pkt_ptr)
{
    if (pkt_ptr[IP_PROTOCOL_POS] == 0x11) {
        if (!memcmp(pkt_ptr + UDP_PAYLOAD, "ECHO", 4)) {
            return true;
        } else if (!memcmp(pkt_ptr + UDP_PAYLOAD, "HASH", 4)) {
            return true;
        } else if (!memcmp(pkt_ptr + UDP_PAYLOAD, "FLOW", 4)) {
            return true;
        } else if (!memcmp(pkt_ptr + UDP_PAYLOAD, "SEQU", 4)) {
            return true;
        } else {
        }
    }

    return false;
}

void
header_swap(uint8_t *pkt_ptr)
{
    swap_ether_header(pkt_ptr);
    swap_ip_header(pkt_ptr);
    swap_udp_header(pkt_ptr);

    recalculate_ip_chksum(pkt_ptr);
    recalculate_udp_chksum(pkt_ptr);
}

void recapsulate_pkt(uint8_t *pkt_ptr, int pkt_len)
{
/*
    if (is_prob_pkt(pkt_ptr)) {
        uint64_t ts = cvmx_get_cycle();
        memcpy(pkt_ptr + UDP_PAYLOAD, &ts, sizeof(uint64_t));

        swap_ether_header(pkt_ptr);
        swap_ip_header(pkt_ptr);
        swap_udp_header(pkt_ptr);

        recalculate_ip_chksum(pkt_ptr);
        recalculate_udp_chksum(pkt_ptr);
    } else if (is_echo_pkt(pkt_ptr)) {
        swap_ether_header(pkt_ptr);
        swap_ip_header(pkt_ptr);
        swap_udp_header(pkt_ptr);

        recalculate_ip_chksum(pkt_ptr);
        recalculate_udp_chksum(pkt_ptr);
    } else {
        entity *des = pkt_2_des(pkt_ptr);
        if (des) {
            rebuild_ether_header(pkt_ptr, des);
            rebuild_ip_header(pkt_ptr, des);

            if (pkt_ptr[IP_PROTOCOL_POS] == 0x11) { // UDP
                recalculate_ip_chksum(pkt_ptr);
                recalculate_udp_chksum(pkt_ptr);
            } else { // TCP
                recalculate_ip_chksum(pkt_ptr);
                recalculate_tcp_chksum(pkt_ptr, pkt_len);
            }
        }
    }
    */

    if (is_echo_pkt(pkt_ptr)) {
        swap_ether_header(pkt_ptr);
        swap_ip_header(pkt_ptr);
        swap_udp_header(pkt_ptr);

        recalculate_ip_chksum(pkt_ptr);
        recalculate_udp_chksum(pkt_ptr);
    }
}

void
print_pkt(uint8_t *pkt_ptr, int len)
{
    int i;
    printf("Packet content is: \n");

    for (i = 0; i < len; i++) {
        printf("%x ", pkt_ptr[i]);

        if ( (i != 0) && (!(i % 16)) ) {
            // 16 gives a better view
            printf("\n");
        }
    }

    printf("\n");
}

