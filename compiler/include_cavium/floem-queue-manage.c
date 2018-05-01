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
#include "floem-queue.h"
#include "floem-queue-manage.h"

//#define DEBUG
//#define CHECK
//#define PERF
//#define PERF2
//#define FAST_READ

#define MIN(x,y) (x<y)? x:y
#define MAX(x,y) (x>y)? x:y
#define MAX_QUEUES 32

size_t t_scanread1 = 0, t_scanread2 = 0, t_scanwrite1 = 0, t_scanwrite2 = 0, t_dmaread = 0, t_dmawrite = 0, t_total = 0, t_totalread = 0, t_totalwrite = 0;
uint32_t n_scanread = 0, n_scanwrite = 0, n_dmaread = 0, n_dmawrite = 0;

CVMX_SHARED dma_circular_queue queues[MAX_QUEUES];
CVMX_SHARED int id = 0;

void do_write(dma_circular_queue *q, dma_segment* seg);
void initiate_write(dma_circular_queue *q);
void manage_read(int qid);
void manage_dma_read(int qid);
void manage_write(int qid);
void manage_dma_write(int qid);

void init_dma_circular_queue() {
  id = 0;
  shared_mm_init();
}

CVMX_SHARED circular_queue_lock* manager_queue;
void init_manager_queue(circular_queue_lock* queue) {
    manager_queue = queue;
}

void check_manager_queue() {
    q_buffer buff = dequeue_get(manager_queue);
    while(buff.entry) {
        q_entry_manage* e = buff.entry;
        int qid = e->task;
        int half = e->half;
        dequeue_release(buf, 0);
        dma_circular_queue* q = &queues[qid];
        update_read_ready_bypass(q, half);
        buff = dequeue_get(manager_queue);
    }
}

int create_dma_circular_queue(uint64_t addr, int size, int overlap, 
			      int (*ready_scan)(void*), int (*done_scan)(void*), bool skip) {
  int my_id, i;
  assert(overlap <= BUFF_SIZE);
  assert(4*BUFF_SIZE <= size);

  printf("create_dma_circular_queue: id = %d\n", id);

  dma_circular_queue *q = &queues[id];
  q->id = id;
  q->skip = skip;
  q->size = size;
  q->overlap = overlap;
  q->block_size = (BUFF_SIZE/overlap) * overlap;
  q->n = 1 + (size-1)/q->block_size;
  q->segments = shared_mm_malloc(sizeof(dma_segment) * q->n);
  q->addr = addr;
  q->read_ready = addr;
  q->write_ready = addr;
  q->read_ready_seg = 0;
  q->write_ready_seg = 0;
  q->write_start_seg = 0;
  q->write_finish_seg = 0;
  q->ready_scan = ready_scan;
  q->done_scan = done_scan;
  spinlock_init(&q->rlock);
  spinlock_init(&q->wlock);

  for(i=0; i<q->n; i++) {
    dma_segment *seg = &q->segments[i];
    seg->id = i;
    seg->count = 0;
    seg->size = MIN(size, q->block_size);
    //seg->size = MIN(BUFF_SIZE, size);
    seg->buf = (uint8_t*) cvmx_fpa_alloc(CVM_FPA_DMA_CHUNK_POOL);
    assert(seg->buf);

    seg->addr = addr + i*q->block_size;
    seg->addr_max = seg->addr + seg->size;
    seg->min = seg->max = 0;
    seg->commit_max = 0;
    seg->starttime = cvmx_clock_get_count(CVMX_CLOCK_CORE);
    __SYNC;
    seg->comp = dma_comp_reset();
    seg->status = INVALID;
    size -= q->block_size;
#if 1 //def DEBUG
    printf("segment[%d][%d]: buf = %p, addr = %p\n", id, i, seg->buf, (void*) seg->addr);
#endif
  }
  q->segments[0].min = addr;
  printf("smart queue[%d]: size = %d, overlap = %d, block_size = %d, n = %d, left = %d\n", 
	 id, q->size, q->overlap, q->block_size, q->n, size);
  assert(size <=0 && size > -q->block_size);
  q->last_write = cvmx_clock_get_count(CVMX_CLOCK_CORE);
  q->last_read = addr;
  __SYNC;

  my_id = id;
  id++;
  assert(id <= MAX_QUEUES);
  return my_id;
}

int find_segment(int qid, size_t addr, int size) {
  size_t off1;
  off1 = addr - queues[qid].addr;
  int seg1;
  seg1 = off1/queues[qid].block_size;

#ifdef CHECK
  size_t off2;
  off2 = off1 + size;
  int seg2;
  seg2 = off2/queues[qid].block_size;
  
  if(seg1 < seg2) {
    assert(seg2 == seg1+1);
    assert(size <= queues[qid].overlap);
    //if(seg2 != seg1+1 || size > queues[qid].overlap) set_health(20);
  }
#endif
  return seg1;
}

#define N_CORES 12 // TODO: should be 12
bool no_read(dma_circular_queue* q) {
  __SYNC;
  // Never update read_ready to be equal to write_ready becuase that means the ready portion is none.
  if(q->read_ready < q->write_ready) {
    // q->write_ready - q->read_ready <= q->overlap
    //return (q->write_ready <= q->read_ready + (N_CORES * q->overlap));
    return (q->write_ready_seg <= q->read_ready_seg + 2);
  }
  else {
    // q->size - q->read_ready + q->write_ready <= q->overlap
    //return (q->size + q->write_ready <= q->read_ready + (N_CORES * q->overlap));
    return (q->n + q->write_ready_seg <= q->read_ready_seg + 2);
  }
  return false;
}

void update_read_ready_bypass(dma_circular_queue* q, uint8_t half) {
    printf("update_read_ready_bypass: qid = %d, half = %d\n", q->id, half);
    int stop_seg = q->write_ready_seg-2;
    if(stop_seg < 0) stop_seg += q->n;

    if(half == 1) {
        int read_ready_seg = q->n/2;
        // if old_read_ready_seg < stop_seg < read_ready_seg
        if(stop_seg < read_ready_seg && (q->read_ready_seg <= stop_seg || q->read_ready_seg > read_ready_seg))
            read_ready_seg = stop_seg;
        q->read_ready = q->addr + read_ready_seg * q->block_size;
        q->read_ready_seg = read_ready_seg;
    }
    else if(half == 2) {
        int read_ready_seg = 0;
        if(q->read_ready_seg <= stop_seg) read_ready_seg = stop_seg;
        q->read_ready = q->addr + read_ready_seg * q->block_size;
        q->read_ready_seg = read_ready_seg;
    }
}

int update_read_ready_fast(dma_circular_queue* q) {
  int stop_seg = q->write_ready_seg-2;
  if(stop_seg < 0) stop_seg += q->n;
  dma_segment* seg = &q->segments[q->read_ready_seg];
  int ret = 0, size;
  
  while(q->read_ready_seg != stop_seg && seg->status != READING) {
    uint8_t* buf = seg->buf + (seg->size - q->overlap);
    size = q->ready_scan(buf);

    __SYNC;
    if(size) {
      if(seg->id == q->n-1) {
	    q->read_ready = q->addr;
        q->read_ready_seg = 0;
      }
      else {
	    q->read_ready = seg->addr_max;
        q->read_ready_seg++;
      }
      seg = &q->segments[q->read_ready_seg];
      ret = 1;
    }
    else 
      return ret;
  }
  return ret;
}  


size_t update_read = 0;
int update_read_ready(dma_circular_queue* q) {
  int stop_seg = q->write_ready_seg-2;
  if(stop_seg < 0) stop_seg += q->n;
  dma_segment* seg = &q->segments[q->read_ready_seg];
  uint8_t* buf;
  int size;
  int ret = 0;

  if(q->read_ready_seg == stop_seg || seg->status == READING) return ret;

  buf = seg->buf + (q->read_ready - seg->addr);
  size = q->ready_scan(buf);
  while(size) {
      ret = 1;
#ifdef CHECK
      assert(size > 0);
      //assert(size == q->overlap || size == BUFF_SIZE/2);
#endif
      size = q->overlap;
      q->read_ready += size;
      if(q->read_ready >= q->addr + q->size) {
#ifdef CHECK
	assert(q->read_ready == q->addr + q->size);
#endif
	q->read_ready = q->addr;
	q->read_ready_seg = 0;
#ifdef FAST_READ
	update_read_ready_fast(q);
	return ret;
#else
	seg = &q->segments[q->read_ready_seg];
	buf = seg->buf;
	if(q->read_ready_seg == stop_seg || seg->status == READING) return ret;
#endif
      }
      else if(q->read_ready >= seg->addr + q->block_size) {
#ifdef CHECK
	assert(q->read_ready == seg->addr + q->block_size);
#endif
	q->read_ready_seg++;
#ifdef FAST_READ
	update_read_ready_fast(q);
	return ret;
#else
	seg = &q->segments[q->read_ready_seg];
	buf = seg->buf;
	if(q->read_ready_seg == stop_seg || seg->status == READING) return ret;
#endif
      }
      else {
	buf = buf + size;
      }
    size = q->ready_scan(buf); // TODO: to avoid complication, try size = q->overlap
  }

  __SYNC;
  return ret;
}



#define N_WRITE 256

// update q->write_ready
// if q->write_ready is updated
// case 1: finish segment
// case 2: time - last_write > threshold
size_t update_write = 0;
void print_flag(uint8_t* buff, uint64_t min, uint64_t max, uint32_t n, uint32_t size) {
  uint32_t i;
  printf("flags: ");
  for(i=0;i<n;i++) {
    uint16_t* len = (uint16_t*) (buff + 2);
    printf("%d,%d ", *buff, *len);
    buff = buff + size;
    min += size;
  }
  printf("\nbuff = %p, max = %p\n", buff, (void*) max);
  assert(min == max);
}

int update_write_ready_fast(dma_circular_queue* q, int* ids, int* n) {
  int ret = 0;
  dma_segment* seg = &q->segments[q->write_ready_seg];
  
  //if(seg->max == 0 && q->read_ready_seg != q->write_ready_seg && seg->status == VALID) {
  while(q->read_ready_seg != q->write_ready_seg) {
#ifdef CHECK
    if(seg->min < seg->addr) {
      printf(">>>>>>>>>>> problem! qid = %d, sid = %d, addr = %p, min = %p, max = %p\n", q->id, seg->id, (void*) seg->addr, (void*) seg->min, (void*) seg->max);
      printf(">>>>>>>>>>> read_ready_seg = %d, ready_ready = %p, write_ready_seg = %d, write_ready = %p\n\n", q->read_ready_seg, (void*) q->read_ready, q->write_ready_seg, (void*) q->write_ready);
    }
    assert(seg->min >= seg->addr);
#endif

    int entries = seg->size/q->overlap;
#ifdef CHECK
    if(seg->count > entries) {
      printf("count = %d, entries = %d, qid = %d, sid = %d, addr = %p, min = %p, max = %p!!!!!!!!!!!!!!\n", seg->count, entries, q->id, seg->id, (void*) seg->addr, (void*) seg->min, (void*) seg->max);
    }
#endif

    __SYNC;
    if(seg->count == entries /*__sync_bool_compare_and_swap32(&seg->count, entries, 0)*/) {
      seg->count = 0;
      __SYNC;
      //printf("FAST WRITE: qid = %d, sid = %d\n", q->id, seg->id);
      ids[*n] = q->write_ready_seg;
      *n = (*n) + 1;
      assert(*n < N_WRITE);

      uint64_t addr = seg->addr_max;
      if(seg->id == q->n-1) {
	q->write_ready = q->addr;
        q->write_ready_seg = 0;
      }
      else {
	q->write_ready = addr;
        q->write_ready_seg++;
      }

      seg->max = addr;
#ifdef CHECK
      if(seg->count > 0) printf("seg->count = %d!!!!!!!!!!!!\n", seg->count);
#endif

      seg = &q->segments[q->write_ready_seg];
      seg->min = seg->addr;
      ret = 3;
    }
    else 
      return ret;
  }
  return ret;
}  

int update_write_ready(dma_circular_queue* q, int* ids, int* n) {
  uint8_t* buf;
  int size;
  int ret = 0;
  if(q->write_ready == q->read_ready) return 0;

  dma_segment* seg = &q->segments[q->write_ready_seg];
  buf = seg->buf + (q->write_ready - seg->addr);
  size = q->done_scan(buf);
  while(size) {
      ret = 1;
#ifdef CHECK
      assert(size > 0);
#endif
      size = q->overlap;
      q->write_ready += size;
      seg->max = q->write_ready;

      if(q->write_ready >= q->addr + q->size) {
	seg->count = 0;
#ifdef CHECK
	assert(q->write_ready == q->addr + q->size);
#endif
	assert(*n < N_WRITE); // TODO
	ids[*n] = q->write_ready_seg;
	*n = (*n) + 1;
	ret = 3;

	q->write_ready = q->addr;
	q->write_ready_seg = 0; 
	seg = &q->segments[q->write_ready_seg];
	seg->min = seg->addr;
	//buf = seg->buf;
	update_write_ready_fast(q, ids, n);
	return ret;
      }
      else if(q->write_ready >= seg->addr_max) {
	seg->count = 0;
#ifdef CHECK
	assert(q->write_ready == seg->addr + q->block_size);
#endif
	assert(*n < N_WRITE);
	ids[*n] = q->write_ready_seg;
	*n = (*n) + 1;
	ret = 3;

	q->write_ready_seg++;
	seg = &q->segments[q->write_ready_seg];
	seg->min = q->write_ready;
	//buf = seg->buf;
	update_write_ready_fast(q, ids, n);
	return ret;
      }
      else {
	buf = buf + size;
      }
      if(q->write_ready == q->read_ready) return ret;
    size = q->done_scan(buf); // TODO: to avoid complication, try size = q->overlap
  }

  __SYNC;
  return ret;
}



bool is_read_ready(dma_circular_queue* q, uint64_t addr) {
  __SYNC;
  if(q->write_ready == q->read_ready) return false;
  if(q->write_ready < q->read_ready) return (q->write_ready <= addr && addr < q->read_ready);
  else return (addr >= q->read_ready && addr >= q->write_ready) ||
	 (addr < q->read_ready && addr < q->write_ready);
}

void handle_writing(dma_circular_queue* q, dma_segment* seg) {
  __SYNC;

  // WRITING --> INVALID
  if((seg->status == WRITING) 
     //&& seg->comp && (seg->comp->comp_byte == 0) &&
     && dma_complete(seg->comp) &&
     __sync_bool_compare_and_swap32(&seg->status, WRITING, RELEASE)) {

    dma_release_comp(seg->comp);
    seg->comp = dma_comp_reset();

    if(seg->commit_max >= seg->addr_max) {   
      seg->min = seg->max = 0;                                                                      
      seg->commit_max = 0;
      if(q->write_ready_seg == seg->id) { 
	//printf("Write complete: qid = %d, sid = %d, seg->addr = %p, q->write_ready = %p\n", q->id, seg->id, (void*) seg->addr, (void*) q->write_ready);
	seg->min = q->write_ready;
      }
      q->write_finish_seg = (seg->id + 1) % q->n;
      seg->count = 0;
      __SYNC;
      seg->status = INVALID;
      __SYNC;
      handle_writing(q, &q->segments[q->write_finish_seg]);
    } else {
#ifdef CHECK 
      assert(seg->commit_max > seg->addr);
#endif
      seg->min = seg->commit_max;
      __SYNC;
      seg->status = INVALID;
      __SYNC;
    }  

    //printf("Write complete: qid = %d, sid = %d, min = %p, max = %p, commit = %p\n", q->id, seg->id, (void*) seg->min, (void*) seg->max, (void*) seg->commit_max);

  }
}

void handle_dma_fail(dma_circular_queue* q, dma_segment* seg) {
  __SYNC;
  int old = seg->status;
  // Handle fail DMA
  if((old == WRITING || old == READING) && dma_complete(seg->comp) && 
     (cvmx_clock_get_count(CVMX_CLOCK_CORE) - seg->starttime > DMA_WAIT) &&
     __sync_bool_compare_and_swap32(&seg->status, old, RELEASE)) {
    printf("(%d) DMA FAIL @ prefetch: qid = %d, sid = %d, status = %d, wait = %ld, cycle = %ld\n", cvmx_get_core_num(), q->id, seg->id, old, cvmx_clock_get_count(CVMX_CLOCK_CORE) - seg->starttime, cvmx_clock_get_count(CVMX_CLOCK_CORE));
    //set_health(999);

    dma_release_comp(seg->comp);
    seg->comp = dma_comp_reset();
    __SYNC;
    seg->status = INVALID;

    // if status = INVALID, seg->commit_max = seg->max > seg->addr + q->blocksize
    // then seg->max > q->read_ready then we will never actually issue dma read
    // then we call actual_write_all
    // TODO: should we make this thread in charge of issue another DMA write?
    // Will this be too late? Because it won't detect the failure until we read again.
    if(old == WRITING) {
      do_write(q, seg);
    }
  } 

}

#ifdef PERF
CVMX_SHARED size_t n_read = 0, n_write = 0;
#endif
void prefetch_segment(dma_circular_queue* q, dma_segment* seg) {
  __SYNC;

  // INVALID --> READING
  if(seg->status == INVALID && 
     ((seg->max == 0) || (q->read_ready_seg == seg->id && seg->max <= q->read_ready)) &&
     !no_read(q) && __sync_bool_compare_and_swap32(&seg->status, INVALID, READING)) {
    //assert(seg->size <= 2048);
    
    size_t off = q->read_ready - seg->addr;
    if(off > seg->size) off = 0;
#ifdef CHECK
    //if(off >= 2048) set_health(24);                                                                                                                                                        
    assert(off < 2048);
#endif
    size_t size = seg->size - off;
    seg->starttime = cvmx_clock_get_count(CVMX_CLOCK_CORE);
    __SYNC;
#ifdef PERF2
    size_t t1, t2;
    t1 = cvmx_clock_get_count(CVMX_CLOCK_CORE);
#endif
    seg->comp = dma_read_with_buf(seg->addr + off, size, (void*) (seg->buf + off), 0);
#ifdef PERF2
    t2 = cvmx_clock_get_count(CVMX_CLOCK_CORE);
    t_dmaread += t2 -t1;
    n_dmaread++;
#endif

#ifdef PERF
    n_read++;
#endif
#ifdef DEBUG
    //printf("(%d) actual read: qid = %d, seg = %d, addr = %p, off = %d, cycle = %ld, t = %ld\n", 
    //	   cvmx_get_core_num(), q->id, seg->id, (void*) seg->addr, off, cvmx_clock_get_count(CVMX_CLOCK_CORE), seg->starttime);
#endif

  }
  // Advance write_ready in order to read more.
  /*
  else if(seg->status == INVALID && no_read(q)) {
    initiate_write(q);
  }
  */

  __SYNC;
}

void handle_reading(dma_circular_queue* q, dma_segment* seg) {
  __SYNC;

  // READING --> VALID
  if((seg->status == READING) && dma_complete(seg->comp) &&
     __sync_bool_compare_and_swap32(&seg->status, READING, RELEASE)) {

    dma_release_comp(seg->comp);
    seg->comp = dma_comp_reset();
    __SYNC;

    // Update read_ready
    update_read = 0;
#ifndef RUNTIME
    if(!spinlock_trylock(&q->rlock)) {
#endif

#ifdef PERF2
    size_t t1, t2, t3;
    t1 = cvmx_clock_get_count(CVMX_CLOCK_CORE);
#endif
    int ret = 0;
#ifdef FAST_READ
    ret = update_read_ready_fast(q);
#endif
    
#ifdef PERF2
    t2 = cvmx_clock_get_count(CVMX_CLOCK_CORE);
#endif
    if(!ret) update_read_ready(q);
#ifdef PERF2
    t3 = cvmx_clock_get_count(CVMX_CLOCK_CORE);
    t_scanread1 += t2 - t1;
    t_scanread2 += t3 - t2;
    n_scanread++;
#endif

#ifndef RUNTIME
    spinlock_unlock(&q->rlock);
    }
#endif
    
    __SYNC;

    if(q->read_ready_seg != seg->id) {
      seg->status = VALID;
      __SYNC;
      handle_reading(q, &q->segments[q->read_ready_seg]);
    }
    // TODO
    else {
      seg->status = INVALID;
      __SYNC;
    }
  }
}

void smart_info(int qid, size_t addr, int size) {
  int sid = find_segment(qid, addr, 0);
  dma_circular_queue* q= &queues[qid];
  int nid = (sid+1) % q->n;
  dma_segment *seg = &queues[qid].segments[sid];
  dma_segment *nseg = &queues[qid].segments[nid];
  printf("\naddr: %p, size = %d, no_read = %d, time = %ld\n", (void*) addr, size, no_read(q), cvmx_clock_get_count(CVMX_CLOCK_CORE));
  printf("seg: sid = %d, start = %p, size = %d, status = %d, min = %p, max = %p\n",
	 seg->id, (void*) seg->addr, seg->size, seg->status, (void*) seg->min, (void*) seg->max);
  printf("nseg: nid = %d, start = %p, size = %d, status = %d, min = %p, max = %p\n",
	 nseg->id, (void*) nseg->addr, nseg->size, nseg->status, (void*) nseg->min, (void*) nseg->max);
  printf("queue: qid = %d, read_seg = %d, read_ready = %p, write_seg = %d, write_ready = %p\n",
	 qid, q->read_ready_seg, (void*) q->read_ready, q->write_ready_seg, (void*) q->write_ready);
}

void* smart_dma_read_local(int qid, size_t addr) {
  int sid = find_segment(qid, addr, 0);
  dma_segment *seg = &queues[qid].segments[sid];
  return (void*) (seg->buf + (addr - seg->addr));
}

// Return local pointer to addr if an entry is ready.
// Otherwise return NULL.
void* smart_dma_read(int qid, size_t addr, int size) {
  dma_circular_queue* q= &queues[qid];
  q->last_read = addr;
  __SYNC;
#ifdef CHECK
  assert(size <= q->overlap);
#endif

#ifndef RUNTIME
  manage_read(qid);
  manage_dma_read(qid);
#endif

#ifdef PERF
  static size_t stat_count = 0, stat_sum[5] = {0};
  size_t start, prefetch, handle, check;  start = cvmx_clock_get_count(CVMX_CLOCK_CORE);

  static size_t hit = 0, miss = 0, lasttime = 0;
  size_t now = core_time_now_us();
  if(now - lasttime > 1000000) {
    printf("read: qid=%d hit = %ld, miss = %ld, reads = %ld\n", qid, hit, miss, n_read);
    hit = miss = n_read = 0;
    lasttime = now;
  }
#endif

  int sid = find_segment(qid, addr, size);
  dma_segment *seg = &q->segments[sid];
  void* ret = NULL;
  if(is_read_ready(q, addr)) {
    ret = (void*) (seg->buf + (addr - seg->addr));
  }

#ifdef PERF
  check = cvmx_clock_get_count(CVMX_CLOCK_CORE);
  stat_count++;
  stat_sum[0] += prefetch - start;
  stat_sum[1] += handle - prefetch;
  stat_sum[2] += check - handle;
  
  if(stat_count == 1000000) {
    printf("============== smart read ==============\n");
    printf("prefetch:  %f\n", 1.0*stat_sum[0]/stat_count);
    printf("handle:    %f\n", 1.0*stat_sum[1]/stat_count);
    printf("check:     %f\n", 1.0*stat_sum[2]/stat_count);
    stat_sum[0] = stat_sum[1] = stat_sum[2] = stat_sum[3] = stat_sum[4] = 0;
    stat_count = 0;
  }

  if(ret) {
    hit++;
    return ret;
  }
  miss++;

#endif
  if(ret) return ret;

  //if(addr >= q->read_ready) 
  __sync_bool_compare_and_swap32(&seg->status, VALID, INVALID);
  return NULL;
}

void do_write(dma_circular_queue *q, dma_segment *seg) {
  size_t min, max;
  uint32_t old = seg->status;
  __SYNC;
  min = seg->min;
  max = seg->max;
#ifdef CHECK
  assert(min <= max);
#endif
  // VALID, INVALID --> WRITING                                                                                                                                                                                            
  if(min < max && (old == VALID || old == INVALID) &&
     __sync_bool_compare_and_swap32(&seg->status, old, WRITING)) {

#ifdef CHECK
    //if((min - seg->addr) > 2048) set_health(26);
    assert(min > 0);
    assert((min - seg->addr) < 2048);
    //if((max - seg->addr) <= 0 || (max - seg->addr) > 2048) set_health(27);
    assert((max - seg->addr) > 0 && (max - seg->addr) <= 2048);
#endif
    if(max == seg->addr_max && seg->commit_max < max)  // need to check seg->commit_max because of DMA failure case
      q->write_start_seg = (seg->id + 1) % q->n;

    seg->commit_max = max;
    seg->starttime = cvmx_clock_get_count(CVMX_CLOCK_CORE);
    __SYNC;
#ifdef PERF2
    size_t t1, t2;
    t1 = cvmx_clock_get_count(CVMX_CLOCK_CORE);
#endif
    seg->comp = dma_write(min, max - min, seg->buf + (min - seg->addr), 0);
#ifdef PERF2
    t2 = cvmx_clock_get_count(CVMX_CLOCK_CORE);
    t_dmawrite += t2 - t1;
    n_dmawrite++;
#endif

#ifdef PERF
    n_write++;
#endif
    __SYNC;
#ifdef DEBUG
    printf("(%d) actual write: q = %d, seg = %p, addr = %p, min = %p, max= %p, cycle = %ld, t = %ld\n", cvmx_get_core_num(), q->id, seg, (void*) seg->addr, (void*) min, (void*) max, cvmx_clock_get_count(CVMX_CLOCK_CORE), seg->starttime);
    /*
    struct tuple *t, *end;
    t = (struct tuple*) (seg->buf + (min - seg->addr));
    end = (struct tuple*) (seg->buf + (max - seg->addr));
    while(t < end) {
      printf("%d ", t->task);
      t++;
    }
    printf("\n");
    */
#endif
  }
}

void initiate_write(dma_circular_queue *q) {
  int ids[N_WRITE], n = 0;
  int ret;

#ifdef PERF
  static size_t full = 0, part = 0, lasttime = 0;
  static size_t stat_count = 0, stat_sum[5] = {0};
  size_t start, update, write;
#endif

#ifndef RUNTIME
  if(!spinlock_trylock(&q->wlock)) {
#endif

#ifdef PERF
    start = cvmx_clock_get_count(CVMX_CLOCK_CORE);
#endif

    update_write = 0;
#ifdef PERF2
    uint64_t t1, t2, t3;
    t1 = cvmx_clock_get_count(CVMX_CLOCK_CORE);
#endif
    ret = update_write_ready_fast(q, ids, &n);
#ifdef PERF2
    t2 = cvmx_clock_get_count(CVMX_CLOCK_CORE);
#endif
    if(!ret && q->write_gap > WRITE_WAIT)
      ret = update_write_ready(q, ids, &n);
#ifdef PERF2
    t3 = cvmx_clock_get_count(CVMX_CLOCK_CORE);
    t_scanwrite1 += t2 - t1;
    t_scanwrite2 += t3 - t2;
    n_scanwrite++;
#endif

#ifndef RUNTIME
    spinlock_unlock(&q->wlock);
  }
#endif
}


void exe_write(dma_circular_queue *q, dma_segment* seg) {
  int old = seg->status;

  if(seg->commit_max < seg->max && (old == VALID || old == INVALID)) {
    do_write(q, seg);
    if(seg->id != q->write_start_seg) exe_write(q, &q->segments[q->write_start_seg]);
  }
}

int smart_dma_write(int qid, size_t addr, int size, void* p) {
  dma_circular_queue *q = &queues[qid];
#ifdef DEBUG
  __SYNC;
  printf("(%d) smart write: qid = %d, write_ready_seg = %d, write_ready = %p, addr = %p\n", cvmx_get_core_num(), qid, q->write_ready_seg, (void*) q->write_ready, (void*) addr);
#endif

#ifdef CHECK
  assert(size <= q->overlap);
#endif

  uint64_t now = cvmx_clock_get_count(CVMX_CLOCK_CORE);
  __SYNC;
  q->write_gap = now - q->last_write;
  q->last_write = now;
  __SYNC;

  int sid = find_segment(qid, addr, size);
  dma_segment *seg = &q->segments[sid];

  __sync_fetch_and_add32(&seg->count, 1);
  /*
  uint32_t count = seg->count;
  while(!__sync_bool_compare_and_swap32(&seg->count, count, count+1)) {
    __SYNC;
    count = seg->count;
  }
  */

#ifndef RUNTIME
  manage_write(qid);
  manage_dma_write(qid);
#endif
  return 0;
}

// Decrease refcount
void smart_dma_free(int qid, size_t addr, int size) {
}

size_t t_sum[6] = {0};
void manage_read(int qid) {
  __SYNC;
  dma_circular_queue* q = &queues[qid];

#ifdef PERF2  
  size_t t1, t2, t3, t4;
  t1 = cvmx_clock_get_count(CVMX_CLOCK_CORE);
#endif
  handle_writing(q, &q->segments[q->write_finish_seg]);
#ifdef PERF2
  t2 = cvmx_clock_get_count(CVMX_CLOCK_CORE);
#endif
  if(!q->skip) handle_reading(q, &q->segments[q->read_ready_seg]);
#ifdef PERF2
  t3 = cvmx_clock_get_count(CVMX_CLOCK_CORE);

  t_sum[0] += t2 - t1;
  t_sum[1] += t3 - t2;
#endif
}

void manage_write(int qid) {
  dma_circular_queue* q = &queues[qid];
  //printf("3. write qid = %d\n", qid);
  initiate_write(q);

  static size_t stat_count = 0;
  stat_count++;
}


void manage_dma_read(int qid) {
  dma_circular_queue* q = &queues[qid];
  if(!q->skip) {
    prefetch_segment(q, &q->segments[q->read_ready_seg]);
    prefetch_segment(q, &q->segments[(q->read_ready_seg + 1) % q->n]);
    //prefetch_segment(q, &q->segments[(q->read_ready_seg + 2) % q->n]);
  }
}

void manage_dma_write(int qid) {
  dma_circular_queue* q = &queues[qid];
  exe_write(q, &q->segments[q->write_start_seg]);
}

void smart_dma_manage(int core_id) {
  static int qid = -1, min, max;
  if(qid == -1) {
    min = (core_id*id)/RUNTIME_CORES;
    max = ((core_id + 1) * id)/RUNTIME_CORES;
    qid = core_id;
  }

#ifdef PERF2
  size_t t1, t2, t3;
  t1 = cvmx_clock_get_count(CVMX_CLOCK_CORE);
#endif

  int i;
  // order
  for(i=min; i<max; i++) {
    //for(i=core_id; i<id; i+=4) {
    manage_read(i);
    manage_dma_read(i);
  }
  dma_read_flush();
#ifdef PERF2
  t2 = cvmx_clock_get_count(CVMX_CLOCK_CORE);
#endif
  for(i=min; i<max; i++) {
    //for(i=core_id; i<id; i+=4) {
    manage_write(i);
    manage_dma_write(i);
  }
  dma_write_flush();

#ifdef PERF2
  t3 = cvmx_clock_get_count(CVMX_CLOCK_CORE);
  t_totalread += t2 - t1;
  t_totalwrite += t3 - t2;

  static size_t stat_count = 0;
  stat_count++;
  if(stat_count == 2000000) {
    printf("==================== profile (%d) ====================\n", core_id + 8);
    printf("total read:  %f\n", 1.0*t_totalread/stat_count);
    printf("total write:  %f\n", 1.0*t_totalwrite/stat_count);
    printf("-------\n");
    int i;
    for(i=0;i<2;i++) {
      printf("read %d: %f\n", i, 1.0*t_sum[i]/stat_count);
      t_sum[i] = 0;
    }
    stat_count = t_total = t_totalread = t_totalwrite = 0;
  }

  if(n_scanread == 1000000) {
    printf(">>>>>>>>>>>>>>> (%d) scan read1: %f\n", core_id+8, 1.0*t_scanread1/n_scanread);
    printf(">>>>>>>>>>>>>>> (%d) scan read2: %f\n", core_id+8, 1.0*t_scanread2/n_scanread);
    t_scanread1 = t_scanread2 = n_scanread = 0;
  }
  if(n_scanwrite == 10000000) {
    printf(">>>>>>>>>>>>>>> (%d) scan write1: %f\n", core_id+8, 1.0*t_scanwrite1/n_scanwrite);
    printf(">>>>>>>>>>>>>>> (%d) scan write2: %f\n", core_id+8, 1.0*t_scanwrite2/n_scanwrite);
    t_scanwrite1 = t_scanwrite2 = n_scanwrite = 0;
  }
  if(n_dmaread == 1000000) {
    printf(">>>>>>>>>>>>>>> (%d) dma read: %f\n", core_id+8, 1.0*t_dmaread/n_dmaread);
    t_dmaread = n_dmaread = 0;
  }
  if(n_dmawrite == 1000000) {
    printf(">>>>>>>>>>>>>>> (%d) dma write: %f\n", core_id+8, 1.0*t_dmawrite/n_dmawrite);
    t_dmawrite = n_dmawrite = 0;
  }
#endif
}

