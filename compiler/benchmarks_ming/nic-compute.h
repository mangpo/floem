/*
 * In-NIC compute header
 */
#ifndef _NIC_COMPUTE_H
#define _NIC_COMPUTE_H
#include <stdbool.h>

typedef enum _TYPE {
    ECHO, /* echo */
    HASH, /* hash computing */
    FLOW, /* flow classification */
    SEQU, /* sequencer */
} PKT_TYPE;

void lock_group_init(cvmx_spinlock_t*);
static PKT_TYPE pkt_parser(uint8_t *pkt_ptr);
static void crypto_3des_initialize(const uint64_t *key);
static void crypto_3des_encrypt(uint64_t *data, int data_len);

#endif /* _NIC_COMPUTE_H */
