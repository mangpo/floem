#ifndef NICIF_H_
#define NICIF_H_
#include <stdint.h>
#define DATA_REGION_NAME "/mykvs_data"
#define INFO_REGION_NAME "/mykvs_info"
#define CORE_REGION_NAME "/mykvs_core%02u"
#define CORE_REGION_NAMEMAX 16
#define INFO_NRETA 128
#define SEG_ITEMHDRSZ 24


struct info_region {
    uint32_t cores;
    uint32_t hash_key[10];
    uint8_t reta[INFO_NRETA];
    uint8_t pad[0x1000 - 44 - INFO_NRETA];
} __attribute__((packed));
struct core_region {
    uint32_t cq_off;
    uint32_t cq_len;
    uint32_t eq_off;
    uint32_t eq_len;
    uint8_t pad[0x1000 - 16];
} __attribute__((packed));
#define CQE_ALIGN 8U
#define CQE_FLAG_HWOWN 0x0001
#define CQE_TYPE_SHIFT 8
#define CQE_TYPE_MASK  0xFF00
#define CQE_TYPE_NOP   0x00
#define CQE_TYPE_GRESP 0x01
#define CQE_TYPE_SRESP 0x02
#define CQE_TYPE_ERR   0x03
#define CQE_TYPE_LOG   0x04
struct cq_entry {
    uint16_t flags;
    //uint16_t len;
} __attribute__((packed));
struct cqe_send_getresponse {
    uint16_t flags;
    //uint16_t len;
    //uint32_t client;
    //uint32_t vallen;
    //uint32_t keylen;
    uint64_t opaque;
    //uint64_t item;
    void* item;
} __attribute__((packed));
struct cqe_send_setresponse {
    uint16_t flags;
    //uint16_t len;
    //uint32_t client;
    uint64_t opaque;
} __attribute__((packed));
struct cqe_send_error {
    uint16_t flags;
    uint16_t len;
    uint16_t datalen;
    uint16_t error;
    uint64_t opaque;
    uint8_t data[];
} __attribute__((packed));
struct cqe_add_logseg {
    uint16_t flags;
    //uint16_t len;
    //uint32_t pad0;
    //uint64_t segbase;
    //uint64_t seglen;
    void* segment;
} __attribute__((packed));
#define EQE_ALIGN 8U
#define EQE_FLAG_SWOWN 0x0001
#define EQE_TYPE_SHIFT 8
#define EQE_TYPE_MASK  0xFF00
#define EQE_TYPE_NOP   0x00
#define EQE_TYPE_RXGET 0x01
#define EQE_TYPE_RXSET 0x02
#define EQE_TYPE_SEGFULL 0x03
struct eq_entry {
    uint16_t flags;
    //uint16_t len;
} __attribute__((packed));
struct eqe_rx_get {
    uint16_t flags;
    //uint16_t len;
    //uint32_t client;
    uint64_t opaque;
    uint32_t hash;
    uint16_t keylen;
    uint8_t key[];
} __attribute__((packed));
struct eqe_rx_set {
    uint16_t flags;
    //uint16_t len;
    //uint32_t client;
    uint64_t opaque;
    void* item;
} __attribute__((packed));
struct eqe_seg_full {
    uint16_t flags;
    //uint16_t len;
    //uint32_t pad0;
    uint64_t last;
} __attribute__((packed));
#endif // ndef NICIF_H_