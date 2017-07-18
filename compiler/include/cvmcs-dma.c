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


inline uint16_t nic_htons(uint16_t x)
{
  uint8_t *s = (uint8_t *)&x;
  return (uint16_t)(s[1] << 8 | s[0]);
}

inline uint16_t nic_ntohs(uint16_t x) {
  return nic_htons(x);
}

inline uint32_t nic_htonl(uint32_t x)
{
  uint8_t *s = (uint8_t *)&x;
  return (uint32_t)(s[3] << 24 | s[2] << 16 | s[1] << 8 | s[0]);
}

inline uint32_t nic_ntohl(uint32_t x) {
  return nic_htonl(x);
}

inline uint64_t nic_htonp(uint64_t x)
{
  uint8_t *s = (uint8_t *)&x;
  return (uint64_t)((uint64_t) s[7] << 56 | (uint64_t) s[6] << 48 | (uint64_t) s[5] << 40 | (uint64_t) s[4] << 32 |
		    (uint64_t) s[3] << 24 | (uint64_t) s[2] << 16 | (uint64_t) s[1] << 8 | s[0]);
}

inline uint64_t nic_ntohp(uint64_t x) {
  return nic_htonp(x);
}


CVMX_SHARED cvmx_spinlock_t dma_read_lock;
CVMX_SHARED cvmx_spinlock_t dma_write_lock;

void init_dma_global_locks() {
  cvmx_spinlock_init(&dma_read_lock);
  cvmx_spinlock_init(&dma_write_lock);
}

int network_send(size_t len, uint8_t *pkt_ptr, int sending_port) {
  int pko_port, corenum, queue, ret;
  cvmx_buf_ptr_t hw_buffer;
  cvmx_pko_command_word0_t pko_command;
  
  // Send to the pko unit
  pko_port = -1;
  corenum = cvmx_get_core_num();
  
  /* Prepare to send the packet */
#ifdef ENABLE_LOCKLESS_PKO
  queue = cvmx_pko_get_base_queue_per_core(sending_port, corenum);
  cvmx_pko_send_packet_prepare(sending_port, queue, CVMX_PKO_LOCK_NONE);
#else
  /*
   * Begin packet output by requesting a tag switch to atomic.
   * Writing to a packet output queue must be synchronized across cores.
   */
  if (octeon_has_feature(OCTEON_FEATURE_PKND))
    {
      /* PKO internal port is different than IPD port */
      pko_port = cvmx_helper_cfg_ipd2pko_port_base(sending_port);
      queue = cvmx_pko_get_base_queue_pkoid(pko_port);
      queue += (corenum % cvmx_pko_get_num_queues_pkoid(pko_port));
    }
  else
    {
      queue = cvmx_pko_get_base_queue(sending_port);
      queue += (corenum % cvmx_pko_get_num_queues(sending_port));
    }
  cvmx_pko_send_packet_prepare(sending_port, queue, CVMX_PKO_LOCK_ATOMIC_TAG);
#endif
  
  /* Build the PKO buffer pointer */
  hw_buffer.u64 = 0;
  hw_buffer.s.pool = CVMX_FPA_PACKET_POOL;
  hw_buffer.s.size = 0xffff;
  hw_buffer.s.back = 0;
  hw_buffer.s.addr = cvmx_ptr_to_phys2(pkt_ptr);
  
  /* Build the PKO command */
  pko_command.u64 = 0;
  pko_command.s.segs = 1;
  pko_command.s.dontfree = 1;
  pko_command.s.total_bytes = len;
  
  /*
   * Send the packet and wait for the tag switch to complete before
   * accessing the output queue. This ensures the locking required
   * for the queue.
   */
#ifdef ENABLE_LOCKLESS_PKO
  ret = cvmx_pko_send_packet_finish(sending_port, queue, pko_command,
                                    hw_buffer, CVMX_PKO_LOCK_NONE);
#else
  if (octeon_has_feature(OCTEON_FEATURE_PKND)) {
    ret = cvmx_pko_send_packet_finish_pkoid(pko_port, queue,
                                            pko_command, hw_buffer, CVMX_PKO_LOCK_ATOMIC_TAG);
  }
  else {
    ret = cvmx_pko_send_packet_finish(sending_port, queue, pko_command,
                                      hw_buffer, CVMX_PKO_LOCK_ATOMIC_TAG);
  }
#endif
  if (ret)
    printf("Failed to send packet out\n");

  return ret;
}

int dma_read_with_buf(uintptr_t addr, size_t len, void **buf) {
  //printf("dma_read: add = %lx, len = %ld\n", addr, len);
  cvm_dma_comp_ptr_t *comp = NULL;
  cvm_pci_dma_cmd_t pci_cmd;
  cvmx_buf_ptr_t lptr;
  cvm_dma_remote_ptr_t rptr;
  int retval;
  
  // Init the command
  pci_cmd.u64 = 0;
  pci_cmd.s.nr = 1;
  pci_cmd.s.nl = 1;
  pci_cmd.s.pcielport = 0;
  
  // Init the completion word
  comp = cvm_get_dma_comp_ptr();
  if (comp == NULL)
    return -1;
  
  comp->comp_byte = 0xff;
  pci_cmd.s.flags = PCI_DMA_INBOUND | PCI_DMA_PUTWORD;
  pci_cmd.s.ptr = CVM_DRV_GET_PHYS(&comp->comp_byte);
  
  // Init the local buffer pointer
  lptr.u64 = 0;
  if (octeon_has_feature(OCTEON_FEATURE_PKI)) {
    cvmx_buf_ptr_pki_t *lptr_o3 = (cvmx_buf_ptr_pki_t *)&lptr;
    lptr_o3->addr = CVM_DRV_GET_PHYS(*buf);
    lptr_o3->size = len;
  } else {
    lptr.s.addr = CVM_DRV_GET_PHYS(*buf);
    lptr.s.size = len;
  }
  
  // Init the remote buffer pointer
  rptr.s.addr = addr;
  rptr.s.size = len;
  CVMX_SYNCWS;

  cvmx_spinlock_lock(&dma_read_lock);
  if (octeon_has_feature(OCTEON_FEATURE_PKI))
    retval = cvm_pci_dma_recv_data_o3(&pci_cmd, (cvmx_buf_ptr_pki_t *)&lptr, &rptr);
  else
    retval = cvm_pci_dma_recv_data(&pci_cmd, &lptr, &rptr);

  
  // DMA blocking model
  if (retval)
    goto no_read_test;

  while (comp->comp_byte) {
    CVMX_SYNCWS;
    cvmx_wait(10);
  }
  cvm_release_dma_comp_ptr(comp);

  //int* p = (int*) *buf;
  //printf("success: int = %d\n", *p);
 no_read_test:
  cvmx_spinlock_unlock(&dma_read_lock);
  return 0;
}

int dma_read(uintptr_t addr, size_t len, void **buf) {
  
  /*
   * Allocate memory from the FPA to have fast memory access.
   * It returns a 2048B block.
   */
  //printf("dma_read: create buffer\n");
  *buf = (uint8_t *)cvmx_fpa_alloc(CVM_FPA_DMA_CHUNK_POOL);
  if (*buf == NULL)
    return -1;
  //memset(*buf, 0x00, len);  // can't include this line -> error

  return dma_read_with_buf(addr, len, buf);
}

int dma_free(void *buf) {
  cvmx_fpa_free(buf, CVM_FPA_DMA_CHUNK_POOL, 0);
  return 0;
}

int dma_buf_alloc(void **buf) {
  /*
   * Allocate memory from the FPA to have fast memory access.
   * It returns a 2048B block.
   */
  *buf = (void *)cvmx_fpa_alloc(CVM_FPA_DMA_CHUNK_POOL);
  if (*buf == NULL)
    return -1;
  return 0;
}

int dma_write(uintptr_t addr, size_t len, void *buf) {
  printf("dma_write: addr = %lx, len = %ld, buf = %lx\n", addr, len, (uintptr_t) buf);

  cvm_pci_dma_cmd_t cmd; // DMA command
  cvmx_buf_ptr_t lptr; // local buffer
  cvmx_buf_ptr_pki_t *bls;
  cvm_dma_remote_ptr_t rptr; // remote buffer
            
  // Init the command word
  cmd.u64 = 0;
  cmd.s.pcielport = 0;
  cmd.s.nl = cmd.s.nr = 1;
  
  // Init remote buffer pointer
  rptr.s.addr = addr;
  rptr.s.size = len; // size of the buffer
  
  // Init local buffer pointer
  lptr.u64 = 0;
  bls = (cvmx_buf_ptr_pki_t *)&lptr;
  bls->size = rptr.s.size;
  cvmx_spinlock_lock(&dma_write_lock);
  bls->addr = CVM_DRV_GET_PHYS(buf);
  
  // Issue the command via OCTEON3 DMA engine
  cvm_pci_dma_send_data_o3(&cmd, bls, &rptr, NULL, 1);
  cvmx_spinlock_unlock(&dma_write_lock);
  return 0;
}
