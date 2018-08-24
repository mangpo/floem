#include "CAVIUM.h"
#include "cvmcs-nic.h"
#include "floem-queue.h"
#include "floem-cache.h"
#include <cvmx-atomic.h>
#include "floem-util.h"
#include "floem-dma.h"
#include "floem-queue-manage.h"

typedef struct {
    int refcount;
} pipeline_state;

static inline void pipeline_unref(pipeline_state* s) {
    s->refcount--;
    if(s->refcount == 0) {
        free(s);
        //printf("free!\n");
    }
}

static inline void pipeline_ref(pipeline_state* s) {
    s->refcount++;
}


#include "protocol_binary.h"

CVMX_SHARED rx_queue_Storage _rx_queue_Storage0;
rx_queue_Storage* rx_queue_Storage0;

CVMX_SHARED circular_queue _circular_queue0;
circular_queue* circular_queue0;

CVMX_SHARED rx_queue_EnqueueCollection _rx_queue_EnqueueCollection0;
rx_queue_EnqueueCollection* rx_queue_EnqueueCollection0;

void init_state_instances() {
  int corenum = cvmx_get_core_num();
  uintptr_t shm_p = STATIC_ADDRESS_HERE;
  rx_queue_Storage* manage_storage = (rx_queue_Storage *) shm_p;
  shm_p = shm_p + MANAGE_SIZE;
  if(corenum == 0) init_manager_queue((void*) manage_storage);

  rx_queue_Storage0 = (rx_queue_Storage *) shm_p;
  shm_p = shm_p + sizeof(rx_queue_Storage);

  circular_queue0 = &_circular_queue0;
  rx_queue_EnqueueCollection0 = &_rx_queue_EnqueueCollection0;
  if(corenum == 0) {
  memset(circular_queue0, 0, sizeof(circular_queue));
  circular_queue0->len = 32768;
  circular_queue0->id = create_dma_circular_queue((uint64_t) rx_queue_Storage0, sizeof(rx_queue_Storage), 64, enqueue_ready_var, enqueue_done_var, true);
  circular_queue0->queue = rx_queue_Storage0;
  circular_queue0->n1 = 256;
  circular_queue0->n2 = 256;
  circular_queue0->entry_size = 64;
  }

  if(corenum == 0) {
  memset(rx_queue_EnqueueCollection0, 0, sizeof(rx_queue_EnqueueCollection));
  rx_queue_EnqueueCollection0->insts[0] = circular_queue0;
  }

}

void finalize_state_instances() {}

void _rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer_in_entry_save(_rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer *p, q_buffer in_entry_arg0) {
  p->in_entry_arg0 = in_entry_arg0;
}
void _rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer_in_pkt_save(_rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer *p, MyState_compressed0* in_pkt_arg0) {
  p->in_pkt_arg0 = in_pkt_arg0;
}

void main_nic_rx_GetPktBuff0(MyState_compressed0*);
void rx_queue_enq_submit0_from_main_nic_rx_MakeKey0(q_buffer);
void rx_queue_fork0_from_main_nic_rx_MakeKey0(MyState_compressed0*);
void rx_queue_enq_alloc0_from_main_nic_rx_MakeKey0(_rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer*,int,int,MyState_compressed0*);
void main_nic_rx_Drop0();
void rx_queue_fill0_from_main_nic_rx_MakeKey0(q_buffer,MyState_compressed0*);
void main_nic_rx_FromNetFree0(void*,void*);
void main_nic_rx_FromNet0();
void rx_queue_size_qid0_from_main_nic_rx_MakeKey0(_rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer*,MyState_compressed0*);
void main_nic_rx_MakeKey0(size_t,void*,void*,MyState_compressed0*);
void main_nic_rx_GetPktBuff0(MyState_compressed0* _x0) {
  MyState_compressed0 *_state = _x0;
    
        void* pkt = _state->pkt;
        void* pkt_buff = _state->pkt_buff;
        
  main_nic_rx_FromNetFree0(pkt, pkt_buff);
}

void rx_queue_enq_submit0_from_main_nic_rx_MakeKey0(q_buffer buf) {

            enqueue_submit(buf, false);
            
}

void rx_queue_fork0_from_main_nic_rx_MakeKey0(MyState_compressed0* _x2) {
  _rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer *_p_rx_queue_fill0_from_main_nic_rx_MakeKey0 = malloc(sizeof(_rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer));
  MyState_compressed0 *_state = _x2;
    
  rx_queue_size_qid0_from_main_nic_rx_MakeKey0(_p_rx_queue_fill0_from_main_nic_rx_MakeKey0,_state);
  _rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer_in_pkt_save(_p_rx_queue_fill0_from_main_nic_rx_MakeKey0, _state);  rx_queue_fill0_from_main_nic_rx_MakeKey0(_p_rx_queue_fill0_from_main_nic_rx_MakeKey0->in_entry_arg0, _p_rx_queue_fill0_from_main_nic_rx_MakeKey0->in_pkt_arg0);

  free(_p_rx_queue_fill0_from_main_nic_rx_MakeKey0);
}

void rx_queue_enq_alloc0_from_main_nic_rx_MakeKey0(_rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer* _p_rx_queue_fill0_from_main_nic_rx_MakeKey0, int len,  int c,  MyState_compressed0* _state) {

            assert(c < 1);
            circular_queue *q = rx_queue_EnqueueCollection0->insts[c];
            
#ifdef QUEUE_STAT
    static size_t full = 0;
    static struct timeval base, now;
    gettimeofday(&now, NULL);
    if(now.tv_sec >= base.tv_sec + 5) {
        printf("\n>>>>>>>>>>>>>>>>>>>>>>>> QUEUE FULL[rx_queue]: q = %p, full/5s = %ld\n", q, full);
        full = 0;
        base = now;
    }
#endif

#ifndef CAVIUM
    q_buffer buff = { NULL, 0 };
#else
    q_buffer buff = { NULL, 0, 0 };
#endif
    while(buff.entry == NULL) {
        
        buff = enqueue_alloc((circular_queue*) q, len, 0, no_clean);
        
#ifdef QUEUE_STAT
        if(buff.entry == NULL) full++;
#endif
   }
   
                                                                     
  _rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer_in_entry_save(_p_rx_queue_fill0_from_main_nic_rx_MakeKey0, buff);
}

void main_nic_rx_Drop0() {
    
}

void rx_queue_fill0_from_main_nic_rx_MakeKey0(q_buffer _x3, MyState_compressed0* _x4) {
  MyState_compressed0 *_state = _x4;
      q_buffer buff = _x3;
  entry_rx_queue0* e = (entry_rx_queue0*) buff.entry;
  if(e) {
    e->keylen = nic_htons(_state->keylen);
    memcpy(e->_content , _state->key, _state->keylen);
    e->task = 1;
  }  
  rx_queue_enq_submit0_from_main_nic_rx_MakeKey0(buff);
  main_nic_rx_GetPktBuff0(_state);
}

void main_nic_rx_FromNetFree0(void* p,  void* buf) {

        
}

void main_nic_rx_FromNet0(cvmx_wqe_t *wqe) {
  MyState_compressed0 *_state = (MyState_compressed0 *) malloc(sizeof(MyState_compressed0));
  _state->refcount = 1;
    
    void* p = cvmx_phys_to_ptr(wqe->packet_ptr.s.addr);
    size_t size = 0;
    if(p) size = cvmx_wqe_get_len(wqe);
    
  if( p != NULL) { main_nic_rx_MakeKey0(size, p, wqe, _state); }
  else if( p == NULL) { main_nic_rx_Drop0(); }
  pipeline_unref((pipeline_state*) _state);
}

void rx_queue_size_qid0_from_main_nic_rx_MakeKey0(_rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer* _p_rx_queue_fill0_from_main_nic_rx_MakeKey0, MyState_compressed0* _x5) {
  MyState_compressed0 *_state = _x5;
    
  rx_queue_enq_alloc0_from_main_nic_rx_MakeKey0(_p_rx_queue_fill0_from_main_nic_rx_MakeKey0,sizeof(entry_rx_queue0) + _state->keylen, _state->qid, _state);
}

void main_nic_rx_MakeKey0(size_t size,  void* pkt,  void* buff,  MyState_compressed0* _state) {

        _state->pkt = pkt;
        _state->pkt_buff = buff;
        
                                        _state->keylen = 32;          _state->key = pkt;
        _state->qid = 0; 
        
  rx_queue_fork0_from_main_nic_rx_MakeKey0(_state);
}

void init(char *argv[]) {
  init_state_instances();
}

void finalize_and_check() {
  finalize_state_instances();
}


void run_threads() {

#ifdef RUNTIME
    {
        int corenum = cvmx_get_core_num();
        if(corenum >= RUNTIME_START_CORE) smart_dma_manage(corenum - RUNTIME_START_CORE);
        if(corenum == RUNTIME_START_CORE) check_manager_queue();
    }
#endif
        }

int get_wqe_cond() {
    int corenum = cvmx_get_core_num();
    return (corenum == 0);
}
    
void run_from_net(cvmx_wqe_t *wqe) {
    main_nic_rx_FromNet0(wqe);
}
    void kill_threads() {
}

