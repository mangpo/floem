/*
 * In-NIC compute header
 */
#ifndef _NIC_COMPUTE_H
#define _NIC_COMPUTE_H
#include <stdbool.h>
#include "pkt-utils.h"

#ifdef CAVIUM
#include "util.h"
#else
#include <dpdkif.h>
#endif

typedef enum _TYPE {
    ECHO, /* echo */
    HASH, /* hash computing */
    FLOW, /* flow classification */
    SEQU, /* sequencer */
} PKT_TYPE;

void lock_group_init(spinlock_t*, int);
PKT_TYPE pkt_parser(uint8_t *pkt_ptr);
void crypto_3des_initialize(const uint64_t *key);
void crypto_3des_encrypt(uint64_t *data, int data_len);
void compute_3des(uint8_t *pkt_ptr, int pkt_len);
void compute_aes(uint8_t *pkt_ptr, int pkt_len);

#define MIN(a,b) (((a)>(b))?(b):(a))
#define MAX(a,b) (((a)>(b))?(a):(b))

#endif /* _NIC_COMPUTE_H */
