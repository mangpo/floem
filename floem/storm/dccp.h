#ifndef DCCP_H
#define DCCP_H

#include "worker.h"
#include <netinet/in.h>

#define MAX(a,b) ((a) < (b) ? (b) : (a))

/** Ethernet header */
struct eth_hdr {
#if ETH_PAD_SIZE
  uint8_t padding[ETH_PAD_SIZE];
#endif
  struct eth_addr dest;
  struct eth_addr src;
  uint16_t type;
} __attribute__ ((packed));

#define SIZEOF_ETH_HDR (14 + ETH_PAD_SIZE)

typedef struct ip_addr ip_addr_p_t;

struct ip_hdr {
  /* version / header length */
  uint8_t _v_hl;
  /* type of service */
  uint8_t _tos;
  /* total length */
  uint16_t _len;
  /* identification */
  uint16_t _id;
  /* fragment offset field */
  uint16_t _offset;
  /* time to live */
  uint8_t _ttl;
  /* protocol*/
  uint8_t _proto;
  /* checksum */
  uint16_t _chksum;
  /* source and destination IP addresses */
  ip_addr_p_t src;
  ip_addr_p_t dest;
} __attribute__ ((packed));

#define IPH_V(hdr)  ((hdr)->_v_hl >> 4)
#define IPH_HL(hdr) ((hdr)->_v_hl & 0x0f)
#define IPH_TOS(hdr) ((hdr)->_tos)
#define IPH_LEN(hdr) ((hdr)->_len)
#define IPH_ID(hdr) ((hdr)->_id)
#define IPH_OFFSET(hdr) ((hdr)->_offset)
#define IPH_TTL(hdr) ((hdr)->_ttl)
#define IPH_PROTO(hdr) ((hdr)->_proto)
#define IPH_CHKSUM(hdr) ((hdr)->_chksum)

#define IPH_VHL_SET(hdr, v, hl) (hdr)->_v_hl = (((v) << 4) | (hl))
#define IPH_TOS_SET(hdr, tos) (hdr)->_tos = (tos)
#define IPH_LEN_SET(hdr, len) (hdr)->_len = (len)
#define IPH_ID_SET(hdr, id) (hdr)->_id = (id)
#define IPH_OFFSET_SET(hdr, off) (hdr)->_offset = (off)
#define IPH_TTL_SET(hdr, ttl) (hdr)->_ttl = (uint8_t)(ttl)
#define IPH_PROTO_SET(hdr, proto) (hdr)->_proto = (uint8_t)(proto)
#define IPH_CHKSUM_SET(hdr, chksum) (hdr)->_chksum = (chksum)

#define IP_HLEN 20

#define IP_PROTO_IP      0
#define IP_PROTO_ICMP    1
#define IP_PROTO_IGMP    2
#define IP_PROTO_IPENCAP 4
#define IP_PROTO_UDP     17
#define IP_PROTO_UDPLITE 136
#define IP_PROTO_TCP     6
#define IP_PROTO_DCCP	 33

#define ETHTYPE_IP        0x0800U

#define DCCP_TYPE_DATA	2
#define DCCP_TYPE_ACK	3

struct dccp_hdr {
  uint16_t src, dst;
  uint8_t data_offset;
  uint8_t ccval_cscov;
  uint16_t checksum;
  uint8_t res_type_x;
  uint8_t seq_high;
  uint16_t seq_low;
} __attribute__ ((packed));

struct dccp_ack {
  struct dccp_hdr hdr;
  uint32_t ack;
} __attribute__ ((packed));

struct pkt_dccp_headers {
    struct eth_hdr eth;
    struct ip_hdr ip;
    struct dccp_hdr dccp;
} __attribute__ ((packed));

struct pkt_dccp_ack_headers {
    struct eth_hdr eth;
    struct ip_hdr ip;
    struct dccp_ack dccp;
} __attribute__ ((packed));

struct connection {
  int32_t cwnd, pipe;
  int32_t seq;
  int32_t lastack;
  size_t acks;
} __attribute__ ((aligned (64)));

void init_header_template(struct pkt_dccp_headers *p);
void init_congestion_control(struct connection* connections);

#endif
