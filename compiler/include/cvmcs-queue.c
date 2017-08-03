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

void no_clean(q_buffer buff) {}

void enqueue_clean(circular_queue* q, void(*clean_func)(q_buffer)) {
    size_t clean, qlen;
    q_entry *eqe;
    void *eq;
    uintptr_t addr;

    clean = q->clean;
    qlen = q->len;
    eq = q->queue;
    while (1) {
        addr = (uintptr_t) eq + clean;
        dma_read(addr, sizeof(q_entry), (void**) &eqe);
	    //check_flag(eqe, clean, "clean");
        //printf("clean: %ld %ld %d\n", clean, off, eqe->flags);
        if ((nic_htons(eqe->flags) & FLAG_MASK) != FLAG_CLEAN) {
            break;
        }
        q_buffer temp = { eqe, addr };
        clean_func(temp);
        eqe->flags = 0;
        dma_write(addr, sizeof(q_entry), eqe);
        dma_free(eqe);
        clean = (clean + eqe->len) % qlen;
    }
    q->clean = clean;
}


q_buffer enqueue_alloc(circular_queue* q, size_t len, void(*clean)(q_buffer)) {
    printf("enq: queue = %p\n", q->queue);
    uint16_t flags, elen;
    uintptr_t addr, dummy_addr;
    q_entry *eqe, *dummy, *current;
    size_t off, qlen, total, eqe_off;
    void *eq;

    /* Align to header size */
    len = (len + ALIGN - 1) & (~(ALIGN - 1));
    eq = q->queue;
    eqe_off = off = q->offset;
    qlen = q->len;
    addr = (uintptr_t) eq + off;
    total = 0;
    dma_read(addr, len + sizeof(q_entry), (void**) &eqe);
    current = eqe;
    do {
        flags = nic_htons(current->flags);
        elen= nic_htons(current->len);
        if ((flags & (FLAG_OWN | FLAG_INUSE)) != 0) {
            q->offset = eqe_off;
            printf("enq_alloc (NULL): entry = %p, offset = %ld, flag = %d\n", (void*) eqe, q->offset, flags);
            dma_free(eqe);
            q_buffer buff = { NULL, 0 };
            return buff;
        }
        enqueue_clean(q, clean);
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
	      dma_read(addr, len + sizeof(q_entry), (void**) &eqe);
	      current = eqe;
            } else {
	      off = off + elen;
	      current = (q_entry*) ((uintptr_t) current + elen);
            }
        }
    } while (total < len);
    /* Too much space, split up and create dummy entry */
    if (total > len) {
      assert(total - len >= sizeof(q_entry));
      dummy_addr = addr + len;
      dummy = (q_entry*) ((uintptr_t) eqe + elen);
      //dma_read(dummy_addr, sizeof(q_entry), (void**) &dummy);
      dummy->flags = 0;
      dummy->len = nic_ntohs(total - len);
      dma_write(dummy_addr, sizeof(q_entry), dummy); // TODO: combine writes?
      //dma_free(dummy);
    }
    eqe->len = len;
    eqe->flags = nic_ntohs(FLAG_INUSE);
    dma_write(addr, sizeof(q_entry), eqe);
    //printf("enq_alloc (before): offset = %ld, len = %ld, mod = %ld\n", eqe_off, len, qlen);
    q->offset = (eqe_off + len) % qlen;
    printf("enq_alloc: queue = %p, entry = %p, len = %d, offset = %ld\n", q->queue, eqe, eqe->len, q->offset);
    q_buffer ret = { eqe, addr };
    return ret;
}

void enqueue_submit(q_buffer buf)
{
    q_entry *e = buf.entry;
    if(e) {
        uintptr_t addr = buf.addr;
        uint16_t len = e->len;
        printf("enq_submit: entry = %p, len = %d\n", e, len);

        e->flags = (e->flags & nic_ntohs(TYPE_MASK)) | nic_ntohs(FLAG_OWN);
        e->len = nic_ntohs(len);
        printf("content: flags = %d, len = %d\n", e->flags, e->len);
        dma_write(addr, len, e);
        dma_free(e);
        //__sync_fetch_and_or(&e->flags, FLAG_OWN);
    }
}

q_buffer dequeue_get(circular_queue* q) {
    q_entry* eqe;
    uintptr_t addr = (uintptr_t) q->queue + q->offset;
    dma_read(addr, sizeof(q_entry), (void**) &eqe);
    //__sync_synchronize();
    //if(eqe->flags)
    //printf("get: addr = %p, flags = %x\n", (void*) addr, eqe->flags);
    uint16_t flags = nic_htons(eqe->flags);
    if((flags & FLAG_MASK) == FLAG_OWN) {
      eqe->flags |= nic_htons(FLAG_INUSE);
      uint16_t elen = nic_htons(eqe->len);
      printf("dequeue_get (before): addr = %p, entry = %p, len = %d\n", (void*) addr, eqe, elen);
      q->offset = (q->offset + elen) % q->len;
      dma_write(addr, sizeof(q_entry), eqe);
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

void dequeue_release(q_buffer buf, uint8_t flag_clean)
{
    q_entry *e = buf.entry;
    uintptr_t addr = buf.addr;
    e->flags = (e->flags & nic_ntohs(TYPE_MASK)) | nic_ntohs(flag_clean);
    dma_write(addr, sizeof(uint16_t), e);
    dma_free(e);
    //printf("release: entry=%ld\n", e);
    //__sync_fetch_and_and(&e->flags, ~FLAG_OWN);
}
