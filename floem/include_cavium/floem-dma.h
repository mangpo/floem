#ifndef FLOEM_DMA_H
#define FLOEM_DMA_H
#include "cvmcs-nic.h"
#include "floem-util.h"

int dma_free(void *buf);
int dma_buf_alloc(void **buf);
int dma_read(uintptr_t addr, size_t len, void **buf);
#ifdef RUNTIME
int dma_comp_reset();
int dma_read_with_buf(uintptr_t addr, size_t len, void *buf, bool block);
int dma_write(uint64_t remote_addr, uint64_t size, void *local_buf, bool block);
int dma_comp_reset();
void dma_release_comp(int);
bool dma_complete(int);
#else
cvm_dma_comp_ptr_t *dma_comp_reset();
cvm_dma_comp_ptr_t *dma_read_with_buf(uintptr_t addr, size_t len, void *buf, bool block);
cvm_dma_comp_ptr_t *dma_write(uint64_t remote_addr, uint64_t size, void *local_buf, bool block);
cvm_dma_comp_ptr_t *dma_comp_reset();
void dma_release_comp(cvm_dma_comp_ptr_t *);
bool dma_complete(cvm_dma_comp_ptr_t *);
#endif

void dma_read_flush();
void dma_write_flush();
  
#endif
