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


/* Functions to measure time using core clock in nanoseconds */
unsigned long long core_time_now_ns()
{
        unsigned long long t;
        t = cvmx_clock_get_count(CVMX_CLOCK_CORE);
        t = 1000000000ULL * t / cvmx_clock_get_rate(CVMX_CLOCK_CORE);
	return t;
}

/* Functions to measure time using core clock in microseconds */
uint64_t core_time_now_us()
{
        unsigned long long t;
        t = cvmx_clock_get_count(CVMX_CLOCK_CORE);
        t = 1000000ULL * t / cvmx_clock_get_rate(CVMX_CLOCK_CORE);
	return t;
}


q_buffer enqueue_alloc(circular_queue* q, size_t len) {
    printf("enq: queue = %p\n", q->queue);
    uint16_t flags, elen;
    uintptr_t addr, dummy_addr;
    q_entry *eqe, *dummy;
    size_t off, qlen, total, eqe_off;
    void *eq;

    /* Align to header size */
    len = (len + ALIGN - 1) & (~(ALIGN - 1));
    eq = q->queue;
    eqe_off = off = q->offset;
    qlen = q->len;
    addr = (uintptr_t) eq + off;
    total = 0;
    do {
        dma_read(addr, sizeof(q_entry), (void**) &eqe);
        flags = nic_htons(eqe->flags);
        elen= nic_htons(eqe->len);
        if ((flags & FLAG_OWN) != 0) {
            q->offset = eqe_off;
            //printf("enq_alloc (NULL): queue = %ld, entry = %ld, flag = %ld\n", q->queue, eqe, *flags);
            dma_free(eqe);
            q_buffer buff = { NULL, 0 };
            return buff;
        }
        //printf("1: total= %ld, len=%ld, elen=%ld\n", total, len, elen);
        /* Never been initialized -> rest of queue is usable */
        if (elen == 0) {
            elen = qlen - off;
        }
        total += elen;
        //printf("2: total= %ld, len=%ld, elen=%ld\n", total, len, elen);
        if (total < len) {
            /* Need more */
            if (off + elen >= qlen) {
                /* No entries wrapping around: create dummy entry from current
                 * entry and start fresh */
	      eqe->len = nic_ntohs(total);
	      eqe->flags = nic_ntohs(FLAG_OWN | TYPE_NOP);
	      dma_write(addr, sizeof(q_entry), eqe);
	      dma_free(eqe);
	      addr = (uintptr_t) eq;
	      eqe_off = off = 0;
	      total = 0;
            } else {
	      off = (off + elen) % qlen;
            }
        }
    } while (total < len);
    /* Too much space, split up and create dummy entry */
    if (total > len) {
      assert(total - len >= sizeof(q_entry));
      dummy_addr = addr + len;
      dma_read(dummy_addr, sizeof(q_entry), (void**) &dummy);
      dummy->flags = 0;
      dummy->len = nic_ntohs(total - len);
      dma_write(dummy_addr, sizeof(q_entry), dummy);
      dma_free(dummy);
    }
    eqe->len = len;
    eqe->flags = 0;
    dma_write(addr, sizeof(q_entry), eqe);
    dma_free(eqe);
    dma_read(addr, len, (void**) &eqe);
    //printf("enq_alloc (before): offset = %ld, len = %ld, mod = %ld\n", eqe_off, len, qlen);
    q->offset = (eqe_off + len) % qlen;
    printf("enq_alloc: queue = %p, entry = %p, len = %d, offset = %ld\n", q->queue, eqe, eqe->len, q->offset);
    q_buffer ret = { eqe, addr };
    return ret;
}

void enqueue_submit(q_buffer buf)
{
    q_entry *e = buf.entry;
    uintptr_t addr = buf.addr;
    uint16_t len = e->len;
    printf("enq_submit: entry = %p, len = %d\n", e, len);

    e->flags |= nic_ntohs(FLAG_OWN);
    e->len = nic_ntohs(len);
    printf("content: flags = %d, len = %d\n", e->flags, e->len);
    dma_write(addr, len, e);
    dma_free(e);
    //__sync_fetch_and_or(&e->flags, FLAG_OWN);
}

q_buffer dequeue_get(circular_queue* q) {
    q_entry* eqe;
    uintptr_t addr = (uintptr_t) q->queue + q->offset;
    dma_read(addr, sizeof(q_entry), (void**) &eqe);
    //__sync_synchronize();
    if(eqe->flags) 
      printf("get: flags = %x\n", eqe->flags);
    if(nic_htons(eqe->flags) & FLAG_OWN) {
      uint16_t elen = nic_htons(eqe->len);
      printf("dequeue_get (before): addr = %p, entry = %p, len = %d\n", (void*) addr, eqe, elen);
      q->offset = (q->offset + elen) % q->len;
      dma_free(eqe);
      dma_read(addr, elen, (void**) &eqe);
      //printf("dequeue_get_return: entry = %ld, offset = %ld\n", eqe, q->offset);
      q_buffer ret = { eqe, addr };
      return ret;
    }
    else {
      dma_free(eqe);
      q_buffer ret = { NULL, 0 };
      return ret;
    }
}

void dequeue_release(q_buffer buf)
{
    q_entry *e = buf.entry;
    uintptr_t addr = buf.addr;
    e->flags &= nic_ntohs(~FLAG_OWN);
    dma_write(addr, sizeof(uint16_t), e);
    dma_free(e);
    //printf("release: entry=%ld\n", e);
    //__sync_fetch_and_and(&e->flags, ~FLAG_OWN);
}

q_buffer next_clean(circular_queue_scan* q) {
    size_t off = q->offset;
    size_t len = q->len;
    size_t clean = q->clean;
    void* base = q->queue;
    //if(c==1 && cleaning.last != off) printf("SCAN: start, last = %ld, offset = %ld, clean = %ld\n", cleaning.last, off, clean);
    q_entry *eqe = NULL;
    uintptr_t addr = 0;
    if (clean != off) {
        addr = (uintptr_t) base + clean;
        dma_read(addr, sizeof(q_entry), (void**) &eqe);
        if ((nic_htons(eqe->flags) & FLAG_OWN) != 0) {
	  dma_free(eqe);
	  eqe = NULL;
        } else {
	  uintptr_t elen = nic_htons(eqe->len);
	  q->clean = (clean + elen) % len;
	  dma_free(eqe);
	  dma_read(addr, elen, (void**) &eqe);
        }
    }
    q_buffer ret = { eqe, addr };
    return ret;
}

void clean_release(q_buffer buf)
{
    q_entry *e = buf.entry;
    dma_free(e);
}
