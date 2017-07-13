#ifndef CVMCS_DMA_H
#define CVMCS_DMA_H
#include "cvmcs-nic.h"

inline uint16_t my_htons(uint16_t x);
inline uint16_t my_ntohs(uint16_t x);
inline uint32_t my_htonl(uint32_t x);
inline uint32_t my_ntohl(uint32_t x);
inline uint64_t my_htonp(uint64_t x);
inline uint64_t my_ntohp(uint64_t x);
void init_dma_global_locks();
int network_send(size_t len, uint8_t *pkt_ptr, int sending_port);
int dma_read_with_buf(uintptr_t addr, size_t len, void **buf);
int dma_read(uintptr_t addr, size_t len, void **buf);
int dma_free(void *buf);
int dma_buf_alloc(void **buf);
int dma_write(uintptr_t addr, size_t len, void *buf);

#endif
