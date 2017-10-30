#include "global-config.h"
#include "octeon-pci-console.h"
#include "cvmcs-common.h"
#include "cvmcs-nic.h"
#include  <cvmx-atomic.h>
#include  <cvmx-access.h>
#include  <cvmx-fau.h>
#include "cvmcs-nic-tunnel.h"
#include "cvmcs-nic-rss.h"
#include "cvmcs-nic-ipv6.h"
#include "cvmcs-nic-ether.h"
#include "cvmcs-nic-mdata.h"
#include "cvmcs-nic-switch.h"
#include "cvmcs-nic-printf.h"
#include "cvm-nic-ipsec.h"
#include "nvme.h"
#include <errno.h>
#include "cvmcs-nic-fwdump.h"
#include "cvmcs-nic-component.h"
#include "cvmcs-nic-hybrid.h"
#include "cvmcs-dcb.h"
#include "generated/cvmcs-nic-version.h"
#include "cvmcs-dma.h"
#include "cvmcs-queue.h"
#include "dma-circular-queue.h"
#include "util.h"

//#define DEBUG

void no_clean(q_buffer buff) {}

static inline void check_flag(uint8_t flag, int offset, const char *s, uint64_t addr) {
#if 1
  if(flag & 0xf0f0) {
    q_entry* dummy;
    dma_read(addr, sizeof(q_entry), (void**) &dummy);
    printf("%s: offset = %d, e->flag = %d, dummy->flag = %d\n", 
	   s, offset, flag, dummy->flag);
    dma_free(dummy);
  }
  //assert((flag & 0xf0) == 0);
#endif
}

void enqueue_clean(q_entry* eqe, uintptr_t addr, void(*clean_func)(q_buffer)) {
  if(eqe->flag == FLAG_CLEAN) {
    q_buffer temp = { eqe, addr, 0 };  // TODO
    clean_func(temp);
  }
}

q_buffer enqueue_alloc(circular_queue* q, size_t len, void(*clean)(q_buffer)) {
    q_entry* eqe;
    uint64_t addr;

    assert(q->offset < q->len);
    assert(len <= q->entry_size);
    addr = (uint64_t) q->queue + q->offset;
#ifdef DMA_CACHE
    eqe = smart_dma_read(q->id, addr, q->entry_size);
#else
    dma_read(addr, q->entry_size, (void**) &eqe);
#endif

    if(eqe->flag == FLAG_CLEAN) enqueue_clean(eqe, addr, clean);
    if(eqe->flag == 0) {
        eqe->len = q->entry_size;  // TODO: does this need htons?
        eqe->flag = FLAG_INUSE;
        eqe->task = 0;

        q->offset += q->entry_size;
        if(q->offset + q->entry_size > q->len) q->offset = 0;
        __SYNC;
        q_buffer buff = { eqe, addr, q->id };
        return buff;
    }

}

void enqueue_submit(q_buffer buf)
{
    q_entry *e = buf.entry;
    if(e) {
        uintptr_t addr = buf.addr;
	    int elen = e->len;
#ifdef DEBUG
        printf("enq_submit: entry = %p, len = %d\n", e, elen);
#endif
	    __SYNC;
        e->flag = FLAG_OWN;
	    e->pad = 0xff;
	    e->checksum = 0;
	    /*
	    uint8_t checksum = 0;
        uint8_t* p = (uint8_t*) e;
        int i;
        for(i=0; i<elen; i++)
	        checksum ^= p[i];
        e->checksum = checksum;
	    */
#ifdef DMA_CACHE
	    smart_dma_write(buf.qid, addr, elen, e);
#else
        dma_write(addr, elen, e, 1);
        dma_free(e);
#endif
    }
}

q_buffer dequeue_get(circular_queue* q) {
    __SYNC;
    q_entry* eqe;
    assert(q->offset < q->len);
    uintptr_t addr = (uintptr_t) q->queue + q->offset;
#ifdef DMA_CACHE
    eqe = smart_dma_read(q->id, addr, q->entry_size);
    if(eqe) {
#else
    dma_read(addr, q->entry_size, (void**) &eqe);
    //if(flag == FLAG_OWN) {
    if(dequeue_ready_var(eqe)) {
      //eqe->flag |= FLAG_INUSE; NO!!!
#endif
        q->offset += q->entry_size;
        if(q->offset + q->entry_size > q->len) q->offset = 0;
        __SYNC;
        q_buffer ret = { eqe, addr, q->id };
        return ret;
    }
    else {
#ifndef DMA_CACHE
      dma_free(eqe);
#endif
      q_buffer ret = { NULL, 0, 0 };
      return ret;
    }
}

void dequeue_release(q_buffer buf, uint8_t flag_clean)
{
    q_entry *e = buf.entry;
    uintptr_t addr = buf.addr;
    __SYNC;
    assert(e->flag == FLAG_OWN);
    e->checksum = e->pad = 0;
    e->flag = flag_clean;
#ifdef DMA_CACHE
    smart_dma_write(buf.qid, addr, sizeof(uint16_t), e);
#else
    dma_write(addr, sizeof(uint16_t), e, 1);
    dma_free(e);
#endif
    //printf("release: entry=%ld\n", e);
}

// Return 1 when entry is empty.
int enqueue_ready_var(void* p) {
  q_entry* e = p;
  uint16_t flag = e->flag;
  if(flag == 0 || flag == FLAG_CLEAN) {
    int size = e->len;
    return (size)? size: BUFF_SIZE/2; // overshooting is fine for reading
  }
  return 0;
}

int enqueue_done_var(void* p) {
  q_entry* e = p;
  uint16_t flag = e->flag;
  __SYNC;
  return (flag == FLAG_OWN)? e->len: 0;
}

// Return 1 when entry is ready to read or being read.
int dequeue_ready_var(void* p) {
  q_entry* e = p;
  if(e->flag == FLAG_OWN && e->pad == 0xff) {
    uint8_t* x = p;
    uint8_t checksum = 0;
    int len = nic_htons(e->len);
    int i;
    for(i=0; i<len; i++)
      checksum ^= x[i];
    //printf(">>>>>> dequeue_ready: checksum = %d\n", checksum);

    return (checksum == 0)? len: 0;
  }
  return 0;
}

int dequeue_done_var(void* p) {
  q_entry* e = p;
  uint16_t flag = e->flag;
  __SYNC;
  /* if(flag == 0 || flag == FLAG_CLEAN) { */
  /*   int deq2_len = nic_htons(e->len); */
  /*   if(deq2_len > 64) printf(">>>>>>>>>>>> deq2_len = %d\n", deq2_len); */
  /*   assert(deq2_len <= 64); */
  /* } */
  return (flag == 0 || flag == FLAG_CLEAN)? nic_htons(e->len): 0;
}
