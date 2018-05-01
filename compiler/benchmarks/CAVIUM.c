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

CVMX_SHARED circular_queue_lock _circular_queue_lock0;
circular_queue_lock* circular_queue_lock0;

CVMX_SHARED rx_queue_EnqueueCollection _rx_queue_EnqueueCollection0;
rx_queue_EnqueueCollection* rx_queue_EnqueueCollection0;

CVMX_SHARED rx_queue_EnqueueCollection _rx_queue_EnqueueCollection0;
rx_queue_EnqueueCollection* rx_queue_EnqueueCollection0;

CVMX_SHARED circular_queue_lock _manager_queue;
circular_queue_lock* manager_queue;

void init_state_instances() {
  int corenum = cvmx_get_core_num();
  uintptr_t shm_p = STATIC_ADDRESS_HERE;

  rx_queue_Storage* manage_storage = (rx_queue_Storage *) shm_p;
  shm_p = shm_p + MANAGE_SIZE;

  rx_queue_Storage0 = (rx_queue_Storage *) shm_p;
  shm_p = shm_p + sizeof(rx_queue_Storage);

  manager_queue = &_manager_queue;
  if(corenum == 0) {
    init_manager_queue(manager_queue);
    memset(manager_queue, 0, sizeof(circular_queue_lock));
    qlock_init(&manager_queue->lock);
    manager_queue->len = MANAGE_SIZE;
    manager_queue->queue = manage_storage;
    manager_queue->entry_size = sizeof(q_entry_manage);
    manager_queue->id = create_dma_circular_queue((uint64_t) manage_storage, MANAGE_SIZE, sizeof(q_entry_manage), dequeue_ready_var, dequeue_done_var, false);
  }

  circular_queue_lock0 = &_circular_queue_lock0;
  rx_queue_EnqueueCollection0 = &_rx_queue_EnqueueCollection0;
  if(corenum == 0) {
  memset(circular_queue_lock0, 0, sizeof(circular_queue_lock));
  qlock_init(&circular_queue_lock0->lock);
  circular_queue_lock0->len = 65536;
  circular_queue_lock0->queue = rx_queue_Storage0;
  circular_queue_lock0->entry_size = 64;
  circular_queue_lock0->id = create_dma_circular_queue((uint64_t) rx_queue_Storage0, sizeof(rx_queue_Storage), 64, enqueue_ready_var, enqueue_done_var, true);
  }

  if(corenum == 0) {
  memset(rx_queue_EnqueueCollection0, 0, sizeof(rx_queue_EnqueueCollection));
  rx_queue_EnqueueCollection0->insts[0] = circular_queue_lock0;
  }

}

void finalize_state_instances() {}

void _rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer_in_entry_save(_rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer *p, q_buffer in_entry_arg0) {
  p->in_entry_arg0 = in_entry_arg0;
}
void _rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer_in_pkt_save(_rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer *p, MyState_compressed0* in_pkt_arg0) {
  p->in_pkt_arg0 = in_pkt_arg0;
}

void rx_queue_enq_submit0_from_main_nic_rx_MakeKey0(q_buffer);
void rx_queue_fork0_from_main_nic_rx_MakeKey0(MyState_compressed0*);
void rx_queue_enq_alloc0_from_main_nic_rx_MakeKey0(_rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer*,int,int,MyState_compressed0*);
void main_nic_rx_MakeKey0();
void rx_queue_fill0_from_main_nic_rx_MakeKey0(q_buffer,MyState_compressed0*);
void rx_queue_size_qid0_from_main_nic_rx_MakeKey0(_rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer*,MyState_compressed0*);
void rx_queue_enq_submit0_from_main_nic_rx_MakeKey0(q_buffer buf) {

            enqueue_submit(buf, false);
            
}

void rx_queue_fork0_from_main_nic_rx_MakeKey0(MyState_compressed0* _x1) {
  _rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer *_p_rx_queue_fill0_from_main_nic_rx_MakeKey0 = malloc(sizeof(_rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer));
  MyState_compressed0 *_state = _x1;
    
  rx_queue_size_qid0_from_main_nic_rx_MakeKey0(_p_rx_queue_fill0_from_main_nic_rx_MakeKey0,_state);
  _rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer_in_pkt_save(_p_rx_queue_fill0_from_main_nic_rx_MakeKey0, _state);  rx_queue_fill0_from_main_nic_rx_MakeKey0(_p_rx_queue_fill0_from_main_nic_rx_MakeKey0->in_entry_arg0, _p_rx_queue_fill0_from_main_nic_rx_MakeKey0->in_pkt_arg0);

  free(_p_rx_queue_fill0_from_main_nic_rx_MakeKey0);
}

void rx_queue_enq_alloc0_from_main_nic_rx_MakeKey0(_rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer* _p_rx_queue_fill0_from_main_nic_rx_MakeKey0, int len,  int c,  MyState_compressed0* _state) {

            assert(c < 1);
            circular_queue_lock *q = rx_queue_EnqueueCollection0->insts[c];
            
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
        qlock_lock(&q->lock);
        buff = enqueue_alloc((circular_queue*) q, len, 0, no_clean);
        qlock_unlock(&q->lock);
#ifdef QUEUE_STAT
        if(buff.entry == NULL) full++;
#endif
   }
   
                                                                     
  _rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer_in_entry_save(_p_rx_queue_fill0_from_main_nic_rx_MakeKey0, buff);
}

void main_nic_rx_MakeKey0() {
  MyState_compressed0 *_state = (MyState_compressed0 *) malloc(sizeof(MyState_compressed0));
  _state->refcount = 1;
    
        _state->key = 99;
        static int qid = 0;
        _state->qid= qid;
        qid = (qid+1) % 1;

        
  rx_queue_fork0_from_main_nic_rx_MakeKey0(_state);
  pipeline_unref((pipeline_state*) _state);
}

void rx_queue_fill0_from_main_nic_rx_MakeKey0(q_buffer _x2, MyState_compressed0* _x3) {
  MyState_compressed0 *_state = _x3;
      q_buffer buff = _x2;
  entry_rx_queue0* e = (entry_rx_queue0*) buff.entry;
  if(e) {
    e->key = nic_htonl(_state->key);
    e->task = 1;
  }  
  rx_queue_enq_submit0_from_main_nic_rx_MakeKey0(buff);
}

void rx_queue_size_qid0_from_main_nic_rx_MakeKey0(_rx_queue_fill0_from_main_nic_rx_MakeKey0_join_buffer* _p_rx_queue_fill0_from_main_nic_rx_MakeKey0, MyState_compressed0* _x4) {
  MyState_compressed0 *_state = _x4;
    
  rx_queue_enq_alloc0_from_main_nic_rx_MakeKey0(_p_rx_queue_fill0_from_main_nic_rx_MakeKey0,sizeof(entry_rx_queue0), _state->qid, _state);
}

void init(char *argv[]) {
  init_state_instances();
}

void finalize_and_check() {
  finalize_state_instances();
}


void _run_main_nic_rx_MakeKey0(int corenum) {

        main_nic_rx_MakeKey0();
            }
void run_threads() {

#ifdef RUNTIME
    {
        int corenum = cvmx_get_core_num();
        if(corenum >= RUNTIME_START_CORE)  smart_dma_manage(corenum - RUNTIME_START_CORE);
        if(corenum == RUNTIME_START_CORE) check_manager_queue();
    }
#endif
        
    {
        int corenum = cvmx_get_core_num();
        if((corenum == 0))  _run_main_nic_rx_MakeKey0(corenum);
    }
        }
int get_wqe_cond() { return 1; }
void run_from_net(cvmx_wqe_t *wqe) {}
void kill_threads() {
}

