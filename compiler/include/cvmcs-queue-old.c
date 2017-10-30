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
#ifdef DEBUG
    printf("enq: queue = %p\n", q->queue);
#endif
    uint16_t flag, elen;
    uintptr_t addr, dummy_addr;
    q_entry *eqe, *dummy, *current;
    size_t off, qlen, total, eqe_off;
    void *eq;

    /* Align to header size */
    __SYNC;
    len = (len + ALIGN - 1) & (~(ALIGN - 1));
    eq = q->queue;
    eqe_off = off = q->offset;
    qlen = q->len;
    addr = (uintptr_t) eq + off;
    total = 0;
    assert(len <= qlen && qlen < 65536);

#ifdef DMA_CACHE
    eqe = smart_dma_read(q->id, addr, sizeof(q_entry));
#else
    dma_read(addr, len + sizeof(q_entry), (void**) &eqe);
#endif
    current = eqe;

#if 1
    static uintptr_t prev_addr = 0;
    static size_t count = 0;

    if(addr != prev_addr) {
      prev_addr = addr;
      count = 0;
    }
#endif

    do {
      if(current == NULL) {
	q->offset = eqe_off;
#ifndef DMA_CACHE
            dma_free(eqe);
#endif
	q_buffer buff = { NULL, 0, 0 };
	return buff;
      }
      //printf("current = %p\n", current);
        flag = current->flag;
        elen= nic_htons(current->len);
	check_flag(flag, off, "enqueue_alloc", addr + total);
        if ((flag & (FLAG_OWN | FLAG_INUSE)) != 0) {
	  //printf("return null\n");
            q->offset = eqe_off;
#if 1 //def DEBUG
	    if(addr == prev_addr) count++;
	    if(count > 100000 && count % 100000 == 0) {
	      printf("enq_alloc (NULL): addr = %p, offset = %ld, flag = %d, len = %ld, count = %ld\n", (void*) addr, q->offset, flag, len, count);
	    }
#endif

#ifndef DMA_CACHE
            dma_free(eqe);
#endif
            q_buffer buff = { NULL, 0, 0 };
            return buff;
        }
	enqueue_clean(current, (uintptr_t) eq + off, clean);

        /* Never been initialized -> rest of queue is usable */
        if (elen == 0) {
            elen = qlen - off;
        }
        total += elen;

        if (total < len) {
            /* Need more */
            if (off + elen >= qlen) {
                /* No entries wrapping around: create dummy entry from current
                 * entry and start fresh */
	      eqe->len = nic_ntohs(total);
	      eqe->task = 0;
	      q_buffer buff = { eqe, addr, q->id };
	      enqueue_submit(buff); // need to fill checksum

/* 	      eqe->flag = FLAG_OWN; */
/* #ifdef DMA_CACHE */
/* 	      smart_dma_write(q->id, addr, sizeof(q_entry), eqe); */
/* #else */
/* 	      dma_write(addr, sizeof(q_entry), eqe, 1); */
/* 	      dma_free(eqe); */
/* #endif */

	      addr = (uintptr_t) eq;
	      eqe_off = off = 0;
	      total = 0;
#ifdef DMA_CACHE
	      eqe = smart_dma_read(q->id, addr, sizeof(q_entry)); 
#else
	      dma_read(addr, len + sizeof(q_entry), (void**) &eqe);
#endif
	      current = eqe;
            } else {
	      off = off + elen;
#ifdef DMA_CACHE
	      current = smart_dma_read(q->id, addr + total, sizeof(q_entry));
#else
	      current = (q_entry*) ((uintptr_t) current + elen);
#endif
            }
        }
	//printf("loop enq\n");
    } while(total < len);

    /* Too much space, split up and create dummy entry */
    if (total > len) {
      assert(total - len >= sizeof(q_entry));
      dummy_addr = addr + len;
#ifdef DMA_CACHE
      dummy = smart_dma_read(q->id, dummy_addr, sizeof(q_entry));
      assert(dummy);
#else
      dummy = (q_entry*) ((uintptr_t) eqe + len);
#endif
      dummy->len = nic_ntohs(total - len);
      __SYNC;
      dummy->flag = 0;
      dummy->task = 0;

#ifdef DMA_CACHE
      // No need to write to CPU yet.
      //smart_dma_write(q->id, dummay_addr, sizeof(q_entry), dummy);
#else
      dma_write(dummy_addr, sizeof(q_entry), dummy, 1); // TODO: combine writes?
#endif
    }

    eqe->len = nic_htons(len);
    eqe->flag = 0; //nic_ntohs(FLAG_INUSE); NO!!!
    eqe->task = 0;
    q->offset = (eqe_off + len) % qlen;
    __SYNC;
#ifdef DEBUG
    printf("enq_alloc: queue = %p, entry = %p, len = %d, offset = %ld\n", q->queue, eqe, eqe->len, q->offset);
#endif
    
    q_buffer ret = { eqe, addr, q->id };
    return ret;
}

void enqueue_submit(q_buffer buf)
{
    q_entry *e = buf.entry;
    if(e) {
        uintptr_t addr = buf.addr;
	int elen = nic_htons(e->len);
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

#define READ_SIZE 256
q_buffer dequeue_get(circular_queue* q) {
    __SYNC;
    q_entry* eqe;
    uintptr_t addr = (uintptr_t) q->queue + q->offset;
#ifdef DMA_CACHE
    eqe = smart_dma_read(q->id, addr, sizeof(q_entry));
    if(eqe) {
#else
    dma_read(addr, READ_SIZE, (void**) &eqe);
    //if(flag == FLAG_OWN) {
    if(dequeue_ready_var(eqe)) {
      //eqe->flag |= FLAG_INUSE; NO!!!
#endif
      uint16_t elen = nic_htons(eqe->len);
#ifdef DEBUG
      printf("dequeue_get (before): addr = %p, entry = %p, len = %d\n", (void*) addr, eqe, elen);
#endif
      q->offset = (q->offset + elen) % q->len;
      //dma_write(addr, sizeof(uint16_t), eqe, 1);
      __SYNC;
#ifdef DMA_CACHE
      q_buffer ret = { eqe, addr, q->id };
      return ret;
#else
      if(elen <= READ_SIZE) {
	q_buffer ret = { eqe, addr, q->id };
	return ret;
      }
      else {
	printf("extra read: elen = %d\n", elen);
	dma_free(eqe);
	dma_read(addr, elen, (void**) &eqe);
	//printf("dequeue_get_return: entry = %ld, offset = %ld\n", eqe, q->offset);
	q_buffer ret = { eqe, addr, q->id };
	return ret;
      }
#endif
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
    int size = nic_htons(e->len);
    return (size)? size: BUFF_SIZE/2; // overshooting is fine for reading
  }
  return 0;
}

int enqueue_done_var(void* p) {
  q_entry* e = p;
  uint16_t flag = e->flag;
  __SYNC;
  if(flag == FLAG_OWN) {
    int enq_len = nic_htons(e->len);
    if(enq_len > 64) printf(">>>>>>>>>>>> enq_len = %d\n", enq_len);
    assert(enq_len <= 64);
  }
  return (flag == FLAG_OWN)? nic_htons(e->len): 0;
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

    if(checksum == 0) {
      int deq_len = nic_htons(e->len);
      if(deq_len > 160) { // 152
    	printf(">>>>>>>>>>>> deq_len = %d, checksum = %d, pad %d\n", deq_len, e->checksum, e->pad);
      }
      assert(deq_len <= 160);
    }

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
