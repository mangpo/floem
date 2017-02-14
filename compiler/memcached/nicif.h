#ifndef NICIF_H
#define NICIF_H
#include <stdint.h>
#include "protocol_binary.h"

typedef struct {
    /** Next item in the hash chain. */
    struct item *next;
    /** Hash value for this item */
    uint32_t hv;
    /** Length of value in bytes */
    uint32_t vallen;
    /** Reference count */
    volatile uint16_t refcount;
    /** Length of key in bytes */
    uint16_t keylen;
    /** Flags (currently unused, but provides padding) */
    uint32_t flags;
} __attribute__((packed)) item;

static inline void *item_value(item *it)
{
    return (void *) ((uintptr_t) (it + 1) + it->keylen);
}

typedef struct {
    uint16_t flags;
    uint16_t len;
    uint32_t client;
    uint32_t vallen;
    uint32_t keylen;
    uint64_t opaque;
    uint64_t item;
} __attribute__((packed)) cqe_send_getresponse;

typedef struct {
    //memcached_udp_header mcudp;
    protocol_binary_request_header mcr;
    uint8_t payload[];
} __attribute__ ((packed)) iokvs_message;

#endif
