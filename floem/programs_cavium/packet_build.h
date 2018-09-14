#ifndef PACKET_BUILD_H
#define PACKET_BUILD_H

static uint16_t
in_chksum(uint16_t *addr, int len)
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

struct _ethhdr {
    uint8_t dest[6];
    uint8_t src[6];
    uint16_t type;
} __attribute__((packed));

static void
rebuild_ether_header(uint8_t *pkt_ptr)
{
    struct _ethhdr my_ethhdr = {
        {0x00, 0x02, 0xc9, 0x4e, 0xe9, 0x38}, // n72 eth4
        {0x00, 0x0f, 0xb7, 0x30, 0x3f, 0x58}, // n35 eth2
        0x0800
    };
    memcpy(pkt_ptr, &my_ethhdr, sizeof(struct _ethhdr));
}

struct _iphdr{
    uint8_t version:4,
            ihl:4;
    uint8_t tos;
    uint16_t tot_len;
    uint16_t id;
    uint16_t flag_off;
    uint8_t ttl;
    uint8_t protocol;
    uint16_t cksum;
    uint8_t saddr[4];
    uint8_t daddr[4];
} __attribute__((packed));

static void
rebuild_ip_header(uint8_t *pkt_ptr)
{
    struct _iphdr my_iphdr = {
        .version = 0x4,
        .ihl = 0x5,
        0x00,
        0x002c,
        0x0000,
        0x4000,
        0x40,
        0x11,
        0x00,
        {0x0a, 0x03, 0x00, 0x23}, // n35
        {0x0a, 0x03, 0x00, 0x48}  // n72
    };
    memcpy(pkt_ptr + 14, &my_iphdr, sizeof(struct _iphdr));
}

struct _udphdr{
    uint16_t sport;
    uint16_t dport;
    uint16_t len;
    uint16_t cksum;
} __attribute__((packed));

static void
rebuild_udp_header(uint8_t *pkt_ptr)
{
    struct _udphdr my_udphdr = {
        0x1234,
        0x26fb,
        0x0018, // udp packet size is 24, which is also related with ip header
        0x0000
    };

    memcpy(pkt_ptr + 34, &my_udphdr, sizeof(struct _udphdr));
}

static void
rebuild_payload(uint8_t *pkt_ptr)
{
    // assume the payload is 16 bytes
    uint8_t *payload;
    payload = (uint8_t *)malloc(sizeof(uint8_t) * 16);

    memset(payload, 0x61, 16);
    memcpy(pkt_ptr + 42, payload, 16);
    free(payload);
}

static void
recalculate_ip_chksum(uint8_t *pkt_ptr)
{
    *(uint16_t*)(pkt_ptr + 24) = 0x0000;
    *(uint16_t*)(pkt_ptr + 24) = in_chksum((uint16_t *)(pkt_ptr + 14), 20);
}

static void
recalculate_udp_chksum(uint8_t *pkt_ptr)
{
    *(uint16_t*)(pkt_ptr + 40) = 0x0000;
}


#endif
