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
#include "cvmx.h"
#include "cvmx-malloc.h"
#include "cvmx-bootmem.h"
#include <errno.h>
#include "cvmcs-nic-fwdump.h"
#include "cvmcs-nic-component.h"
#include "cvmcs-nic-hybrid.h"
#include "cvmcs-dcb.h"
#include "generated/cvmcs-nic-version.h"
#include "floem-util.h"

/************************************************************/
/*                         TIMING                           */
/************************************************************/

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

/************************************************************/
/*                       BYTE ORDER                         */
/************************************************************/

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
  return (uint64_t)((uint64_t) s[7] << 56 | (uint64_t) s[6] << 48 |
                    (uint64_t) s[5] << 40 | (uint64_t) s[4] << 32 |
                    (uint64_t) s[3] << 24 | (uint64_t) s[2] << 16 |
                    (uint64_t) s[1] << 8 | s[0]);
}

inline uint64_t nic_ntohp(uint64_t x) {
  return nic_htonp(x);
}

/************************************************************/
/*                        NETWORK                           */
/************************************************************/

int network_send(size_t len, uint8_t *pkt_ptr, int sending_port) {
  int pko_port, corenum, queue, ret;
  cvmx_buf_ptr_t hw_buffer;
  cvmx_pko_command_word0_t pko_command;

#ifdef DEBUG_PACKET_SEND
  printf("network_send: p = %p, len = %ld\n", pkt_ptr, len);
  size_t i;
  printf("\nsend:");
  for(i=0;i<len;i++) {
    if(i%16==0) printf("\n");
    printf("%x ", pkt_ptr[i]);
  }
  printf("\n\n");
#endif

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
  pko_command.s.dontfree = 1; // 1 - don't free                                                           
 
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

/************************************************************/
/*                     SHARED MEMORY                        */
/************************************************************/

CVMX_SHARED cvmx_arena_list_t my_arena = NULL;

void  
shared_mm_init()
{
    int ret;
    void *shared_mm;

    shared_mm = cvmx_bootmem_alloc_named(MEM_SIZE, 128, "shared_mm");
    if(!shared_mm)
      printf("shared_mm_init: Fail to create shared memory!\n");
    assert(shared_mm);

    ret = cvmx_add_arena(&my_arena, shared_mm, MEM_SIZE);
    if(ret)
      printf("shared_mm_init: Fail to add arena\n");
    assert(ret == 0);
}

void* 
shared_mm_malloc(int size)
{
  assert(size < MEM_SIZE);
    return cvmx_malloc(my_arena, size);
}

void* 
shared_mm_realloc(void *ptr, int size)
{
    return cvmx_realloc(my_arena, ptr, size);
}

void* 
shared_mm_memalign(int size, int alignment)
{
    return cvmx_memalign(my_arena, alignment, size);
}

void  
shared_mm_free(void *ptr)
{
    cvmx_free(ptr);
}

