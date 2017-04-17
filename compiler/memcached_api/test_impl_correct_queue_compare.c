#include "tmp_impl_correct_queue_compare.h"
#include "iokvs.h"

#define NUM_THREADS     4

static struct item_allocator **iallocs;

void settings_init()
{
    settings.udpport = 11211;
    settings.verbose = 1;
    settings.segsize = 4 * 1024; // 2 * 1024 * 1024
    settings.segmaxnum = 512;
    settings.segcqsize = 1024; // 32 * 1024
}


void run_app(void *threadid) {
  long tid = (long)threadid;

  // init worker
  struct item_allocator ia;
  ialloc_init_allocator(&ia);
  iallocs[tid] = &ia;
  // pass ia->cur to NIC
  send_cq(tid, CQE_TYPE_LOG, ia.cur, 0);

  printf("Worker %ld starting\n", tid);

  while(true) {
      eq_entry* e = get_eq(tid);
      //printf("get_eq %ld\n", e);
      if(e == NULL) {
        continue;
        //printf("eq_entry at core %ld is null.\n", tid);
      }
      uint8_t type = (e->flags & EQE_TYPE_MASK) >> EQE_TYPE_SHIFT;
      //printf("get_eq type %d, flag = %d\n", type, e->flags);
      if (type == EQE_TYPE_RXGET) {

        eqe_rx_get* e_get = (eqe_rx_get*) e;
        item *it = hasht_get(e_get->key, e_get->keylen, e_get->hash);
//        printf("get at core %ld: id: %ld, keylen: %d, hash: %d\n", tid, e_get->opaque, e_get->keylen, e_get->hash);
//        printf("get at core %ld: id: %ld, item = %ld.....\n", tid, e_get->opaque, it);
//        uint8_t* key = e_get->key;
//        for(int i=0; i<e_get->keylen; i++)
//            printf("get id: %ld, key[%d] = %d\n", e_get->opaque, i, key[i]);
        uint8_t* val = item_value(it);
        printf("get at core %ld: id: %ld, keylen: %d, vallen %d, val: %d\n", tid, e_get->opaque, it->keylen, it->vallen, val[0]);
        send_cq(tid, CQE_TYPE_GRESP, it, e_get->opaque);
      }
      else if (type == EQE_TYPE_RXSET) {
        eqe_rx_set* e_set = (eqe_rx_set*) e;
        item* it = e_set->item;
        uint8_t * val = item_value(it);
//        printf("set at core %ld: id: %ld, keylen: %d, hash: %d\n", tid, e_set->opaque, it->keylen, it->hv);
        printf("set at core %ld: id: %ld, item: %ld, keylen: %d, vallen: %d, val: %d\n", tid, e_set->opaque, it, it->keylen, it->vallen, val[0]);
//        uint8_t* key = item_key(it);
//        for(int i=0; i<it->keylen; i++)
//            printf("set id: %ld, key[%d] = %d\n", e_set->opaque, i, key[i]);
        hasht_put(it, NULL);
        send_cq(tid, CQE_TYPE_SRESP, NULL, e_set->opaque);
      }
      else if (type == EQE_TYPE_SEGFULL) {
        struct segment_header* segment = new_segment(&ia, false);
        if(segment == NULL) {
            printf("Fail to allocate new segment.\n");
            exit(-1);
        }
        send_cq(tid, CQE_TYPE_LOG, segment, 0);

        eqe_seg_full* e_full = (eqe_seg_full*) e;
        struct segment_header* old = e_full->segment;
        size_t avail = old->size - old->offset;
        segment_item_free(old, avail);
        old->offset += avail;
      }
      release(e);
      usleep(10);
  }
}

void maintenance()
{
    size_t i;
    usleep(1000);
    while (1) {
        for (i = 0; i < NUM_THREADS; i++) {
            ialloc_maintenance(iallocs[i]);
        }
        usleep(10);
    }
}

int main() {
  init();

  // spec
  hasht_init();
  spec_run_threads();
  usleep(500000);
  spec_kill_threads();

  // impl
  settings_init();
  hasht_init();
  ialloc_init();
  iallocs = calloc(NUM_THREADS, sizeof(*iallocs));

  usleep(10);
  pthread_t threads[NUM_THREADS];
  for(int t=0;t<NUM_THREADS;t++) {
       printf("In main: creating thread %d\n", t);
       int rc = pthread_create(&threads[t], NULL, run_app, (void *)t);
       if (rc){
          printf("ERROR; return code from pthread_create() is %d\n", rc);
          exit(-1);
       }
  }

  impl_run_threads();
  //usleep(100000);
  //maintenance();
  usleep(500000);

  for(int t=0;t<NUM_THREADS;t++) {
       int rc = pthread_cancel(threads[t]);
       if (rc){
          printf("ERROR; return code from pthread_cancel() is %d\n", rc);
          exit(-1);
       }
  }
  impl_kill_threads();


  // compare
  finalize_and_check();
  return 0;
}