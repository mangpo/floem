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
#include "floem-util.h"
#include "floem-dma.h"

//#define DEBUG
#define CHECK

/*
int read_count = 0;
int write_count = 0;

int get_read_count() {
  int temp = read_count;
  read_count = 0;
  return temp;
}

int get_write_count() {
  int temp = write_count;
  write_count = 0;
  return temp;
}
*/

#ifdef RUNTIME
#define MAX_READ 4 //4
#define MAX_WRITE 8 //4
#else
#define MAX_READ 1 //4
#define MAX_WRITE 1 //4
#endif

#define MAX_COMP 1028
#define PUSH_CYCLE 1 //10000000

////////// May need to be shared if manage_read/write on different core as manage_dma ///////////
#ifdef RUNTIME
cvm_dma_comp_ptr_t *comps[MAX_COMP] = {0};
int refcount[MAX_COMP] = {0};
int comp_id = 0;

int dma_comp_reset() {
  return -1;
}

bool dma_complete(int myindex) {
  //return (comps[myindex]->comp_byte != 0xff);
  return myindex >= 0 && (comps[myindex]->comp_byte == 0);
}

void dma_release_comp(int myindex) {
  assert(refcount[myindex] > 0);
  int ref;
  ref = __sync_fetch_and_sub32(&refcount[myindex], 1);
  //refcount[myindex]--;
  //if(refcount[myindex] == 0) {
  if(ref == 1) {
    cvm_release_dma_comp_ptr(comps[myindex]);
    comps[myindex] = NULL;
  }
}
#else
cvm_dma_comp_ptr_t *dma_comp_reset() {
  return NULL;
}

bool dma_complete(cvm_dma_comp_ptr_t *comp) {
  //return (comps[myindex]->comp_byte != 0xff);
  return comp && (comp->comp_byte == 0);
}

void dma_release_comp(cvm_dma_comp_ptr_t *comp) {
  cvm_release_dma_comp_ptr(comp);
}
#endif

////////////////////////// Local for each core //////////////////////////////
cvm_dma_comp_ptr_t *comp_r;
cvm_pci_dma_cmd_t pci_cmd_r;
cvmx_buf_ptr_t lptr_r[MAX_READ];
cvm_dma_remote_ptr_t rptr_r[MAX_READ];
int n_read = 0;
uint64_t start_r;

#ifdef RUNTIME
int 
#else
cvm_dma_comp_ptr_t*
#endif
dma_read_with_buf(uintptr_t addr, size_t len, void *buf, bool block) {
  //read_count++;
#ifdef DEBUG
  printf("dma_read: addr = %p, buf = %p, len = %ld\n", (void*) addr, buf, len);
#endif

  int retval;

  retval = 0;

#ifdef CHECK
  assert(buf != NULL);
  assert(len <= 2048);
#endif

#ifdef RUNTIME
  static int myindex = -1;
  if(n_read == 0) {
    if(!block) {
      do {
        comp_id = (comp_id + 1) % MAX_COMP;
      } while(comps[comp_id]);
      myindex = comp_id;
    }
#endif

    // Init the command
    pci_cmd_r.u64 = 0;
    pci_cmd_r.s.pcielport = 0;
    
    // Init the completion word
    comp_r = cvm_get_dma_comp_ptr();
    assert(comp_r != NULL);
    
    comp_r->comp_byte = 0xff;
    pci_cmd_r.s.flags = PCI_DMA_INBOUND | PCI_DMA_PUTWORD;
    pci_cmd_r.s.ptr = CVM_DRV_GET_PHYS(&comp_r->comp_byte);

#ifdef RUNTIME
    if(!block) {
      comps[myindex] = comp_r;
      assert(refcount[myindex] == 0);
    }
    start_r = cvmx_clock_get_count(CVMX_CLOCK_CORE);
  }
  if(!block) 
    __sync_fetch_and_add32(&refcount[myindex], 1);
  //refcount[myindex]++;
#endif
    
  // Init the local buffer pointer
  lptr_r[n_read].u64 = 0;
  if (octeon_has_feature(OCTEON_FEATURE_PKI)) {
    cvmx_buf_ptr_pki_t *lptr_o3 = (cvmx_buf_ptr_pki_t *)&lptr_r[n_read];
    lptr_o3->addr = CVM_DRV_GET_PHYS(buf);
    lptr_o3->size = len;
    //printf("phys addr = %lx\n", (uint64_t) lptr_o3->addr);
  } else {
    lptr_r[n_read].s.addr = CVM_DRV_GET_PHYS(buf);
    lptr_r[n_read].s.size = len;
    //printf("phys addr = %lx\n", (uint64_t) lptr.s.addr);
  }
  
  // Init the remote buffer pointer
  rptr_r[n_read].s.addr = addr;
  rptr_r[n_read].s.size = len;
  CVMX_SYNCWS;
  n_read++;

  //cvmx_spinlock_lock(&dma_read_lock);
  if(block || n_read == MAX_READ) {
    pci_cmd_r.s.nr = n_read;
    pci_cmd_r.s.nl = n_read;
    n_read = 0;
    /* if(!block) { */
    /*   do { */
    /* 	comp_id = (comp_id + 1) % MAX_COMP; */
    /*   } while(comps[comp_id]); */
    /* } */

    int count = 0;
    do {
      if (octeon_has_feature(OCTEON_FEATURE_PKI))
	retval = cvm_pci_dma_recv_data_o3(&pci_cmd_r, (cvmx_buf_ptr_pki_t *)lptr_r, rptr_r);
      else
	retval = cvm_pci_dma_recv_data(&pci_cmd_r, lptr_r, rptr_r);
      count++;
      if(count % 1000 == 0) printf("dma_read stuck: count = %d\n", count);
    } while(retval);
  }
    
  /*
  static size_t stat_count = 0, stat_sum[2] = {0};
  stat_count++;
  stat_sum[0] += (t2 - t1) + (t4 - t3);
  stat_sum[1] += t3 - t2;
  if(stat_count == 100000) {
    printf("shared:     %f\n", 1.0*stat_sum[0]/stat_count);
    printf("not-shared: %f\n", 1.0*stat_sum[1]/stat_count);
    stat_count = stat_sum[0] = stat_sum[1] = 0;
  }
  */

#ifdef CHECK
  assert(retval == 0);
#endif
  
  if (retval)
    goto read_return;

  if(block) {
    int i = 0;
    while ((comp_r->comp_byte == 0xff) && (++i < 10000)) {
      cvmx_wait(10);
      CVMX_SYNCWS;
    }
  }
  
 read_return:
  if(block && comp_r) cvm_release_dma_comp_ptr(comp_r);

#ifdef RUNTIME
  return myindex;
#else
  return comp_r;
#endif
}

void dma_read_flush() {
  if(n_read == 0) return;

  uint64_t now = cvmx_clock_get_count(CVMX_CLOCK_CORE);
  if(now - start_r < PUSH_CYCLE) return;
 
  int retval;
  pci_cmd_r.s.nr = n_read;
  pci_cmd_r.s.nl = n_read;
  n_read = 0;
  
  int count = 0;
  do {
    if (octeon_has_feature(OCTEON_FEATURE_PKI))
      retval = cvm_pci_dma_recv_data_o3(&pci_cmd_r, (cvmx_buf_ptr_pki_t *)lptr_r, rptr_r);
    else
      retval = cvm_pci_dma_recv_data(&pci_cmd_r, lptr_r, rptr_r);
    count++;
    if(count % 1000 == 0) printf("dma_read stuck: count = %d\n", count);
  } while(retval);
}

int dma_read(uintptr_t addr, size_t len, void **buf) {
  
  /*
   * Allocate memory from the FPA to have fast memory access.
   * It returns a 2048B block.
   */
  //printf("dma_read: create buffer\n");
  *buf = (uint8_t *)cvmx_fpa_alloc(CVM_FPA_DMA_CHUNK_POOL);
  if (*buf == NULL) {
    printf("dma_read: null\n");
    assert(0);
    return -1;
  }
  //memset(*buf, 0x00, len);  // can't include this line -> error

  dma_read_with_buf(addr, len, *buf, 1);
  return 0;
}

int dma_free(void *buf) {
  if(buf)
    cvmx_fpa_free(buf, CVM_FPA_DMA_CHUNK_POOL, 0);
  return 0;
}

int dma_buf_alloc(void **buf) {
  /*
   * Allocate memory from the FPA to have fast memory access.
   * It returns a 2048B block.
   */
  *buf = (void *)cvmx_fpa_alloc(CVM_FPA_DMA_CHUNK_POOL);
  if (*buf == NULL) {
    printf("dma_buf_alloc: null\n");
    assert(0);
    return -1;
  }
  return 0;
}

cvm_dma_comp_ptr_t *comp_w;
cvm_pci_dma_cmd_t pci_cmd_w; // DMA command
cvmx_buf_ptr_t lptr_w[MAX_WRITE]; // local buffer
cvm_dma_remote_ptr_t rptr_w[MAX_WRITE]; // remote buffer
int n_write = 0;
uint64_t start_w;

#ifdef RUNTIME
int 
#else
cvm_dma_comp_ptr_t*
#endif
dma_write(uint64_t remote_addr, uint64_t size, void *local_buf, bool block)
{
  //write_count++;
#ifdef DEBUG
  printf("dma_write (%d): addr = %p, len = %ld, cycle = %ld\n", cvmx_get_core_num(), (void*) remote_addr, size, cvmx_clock_get_count(CVMX_CLOCK_CORE));
#endif

    int ret = 0;;

#ifdef CHECK
    assert(local_buf != NULL);
    assert(size <= 2048);
#endif

    if ((!local_buf) || (size > 2048)) {
        ret = -1;
        goto blocked_dma_write_done;
    }

#ifdef RUNTIME
    static int myindex = -1;
    if(n_write == 0) {
      if(!block) {
        do {
          comp_id = (comp_id + 1) % MAX_COMP;
        } while(comps[comp_id]);
	myindex = comp_id;
      }
#endif

      /*
       *  Init the command word
       */
      comp_w = cvm_get_dma_comp_ptr();
      assert(comp_w != NULL);
      comp_w->comp_byte = 0xff;
      
      pci_cmd_w.u64 = 0;
      pci_cmd_w.s.pcielport = 0;
      pci_cmd_w.s.flags = PCI_DMA_OUTBOUND | PCI_DMA_PUTWORD;
      pci_cmd_w.s.ptr = CVM_DRV_GET_PHYS(&comp_w->comp_byte);

#ifdef RUNTIME
      if(!block) {
	comps[myindex] = comp_w;
	assert(refcount[myindex] == 0);
      }
      start_w = cvmx_clock_get_count(CVMX_CLOCK_CORE);
    }
    if(!block)
      __sync_fetch_and_add32(&refcount[myindex], 1);
    //refcount[myindex]++;
#endif
  
    /*
     * Init the remote word
     */
    rptr_w[n_write].s.addr = remote_addr;
    rptr_w[n_write].s.size = size;

    /*
     * Init the local word
     */
    cvmx_buf_ptr_pki_t *bls;
    lptr_w[n_write].u64 = 0;
    bls = (cvmx_buf_ptr_pki_t *)&lptr_w[n_write];
    bls->size = rptr_w[n_write].s.size;
    bls->addr = CVM_DRV_GET_PHYS(local_buf);
    bls->packet_outside_wqe = 0;
    //printf("phys addr = %lx\n", (uint64_t) bls->addr);
    n_write++;

    if(block || n_write == MAX_WRITE) {
      /*
       * Issue the command
       */
      pci_cmd_w.s.nl = n_write;
      pci_cmd_w.s.nr = n_write;
      n_write = 0;
      /* if(!block) { */
      /* 	do { */
      /* 	  comp_id = (comp_id + 1) % MAX_COMP; */
      /* 	} while(comps[comp_id]); */
      /* } */

      int count = 0;
      do {
	ret = cvm_pci_dma_send_data_o3(&pci_cmd_w, (cvmx_buf_ptr_pki_t *) lptr_w, rptr_w, (cvmx_wqe_t *)NULL, 0);
	count++;
	if(count % 1000 == 0) printf("dma_write stuck: count = %d\n", count);
      } while(ret);
    }
      
    /*
     * Wait for the completion word
     */
    if(block) {
      int i = 0;
      while ((comp_w->comp_byte == 0xff) && (++i < 10000)) {
        cvmx_wait(10);
        CVMX_SYNCWS;
      }
    }
    
blocked_dma_write_done:
    /*
     * Free resource
     */
    if (block && comp_w) {
        cvm_release_dma_comp_ptr(comp_w);
    }

#ifdef RUNTIME
    return myindex;
#else
    return comp_w;
#endif
}

void dma_write_flush() {
  if(n_write == 0) return;

  uint64_t now = cvmx_clock_get_count(CVMX_CLOCK_CORE);
  if(now - start_w < PUSH_CYCLE) return;

  pci_cmd_w.s.nl = n_write;
  pci_cmd_w.s.nr = n_write;
  n_write = 0;
  /* do { */
  /*   comp_id = (comp_id + 1) % MAX_COMP; */
  /* } while(comps[comp_id]); */

  int ret, count = 0;
  do {
    ret = cvm_pci_dma_send_data_o3(&pci_cmd_w, (cvmx_buf_ptr_pki_t *) lptr_w, rptr_w, (cvmx_wqe_t *)NULL, 0);
    count++;
    if(count % 1000 == 0) printf("dma_write stuck: count = %d\n", count);
  } while(ret);

}
