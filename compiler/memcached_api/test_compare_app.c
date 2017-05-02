#include "app.h"
#include "iokvs_multiprocesses.h"

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


static size_t clean_log(struct item_allocator *ia, bool idle)
{
    item *it, *nit;
    size_t n;

    if (!idle) {
        /* We're starting processing for a new request */
        ialloc_cleanup_nextrequest(ia);
    }

    n = 0;
    while ((it = ialloc_cleanup_item(ia, idle)) != NULL) {
        n++;
        if (it->refcount != 1) {
            if ((nit = ialloc_alloc(ia, sizeof(*nit) + it->keylen + it->vallen,
                    true)) == NULL)
            {
                fprintf(stderr, "Warning: ialloc_alloc failed during cleanup :-/\n");
                abort();
            }

            nit->hv = it->hv;
            nit->vallen = it->vallen;
            nit->keylen = it->keylen;
            rte_memcpy(item_key(nit), item_key(it), it->keylen + it->vallen);
            hasht_put(nit, it);
            item_unref(nit);
        }
        item_unref(it);
    }
    return n;
}


void run_app(void *threadid) {
  long tid = (long)threadid;

  // init worker
  struct item_allocator ia;
  ialloc_init_allocator(&ia);
  iallocs[tid] = &ia;
  // pass ia->cur to NIC
  send_cq(tid, CQE_TYPE_LOG, get_pointer_offset(ia.cur->data), ia.cur->size, 0);

  printf("Worker %ld starting\n", tid);

  while(true) {
      eq_entry* e = get_eq(tid);
      //if(tid == 1) printf("get_eq %ld\n", e);
      if(e == NULL) {
        clean_log(&ia, true);
        clean_cq(tid);
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
        send_cq(tid, CQE_TYPE_GRESP, get_pointer_offset(it), 0, e_get->opaque);
      }
      else if (type == EQE_TYPE_RXSET) {
        eqe_rx_set* e_set = (eqe_rx_set*) e;
        item* it = get_pointer(e_set->item);
        uint8_t * val = item_value(it);
//        printf("set at core %ld: id: %ld, keylen: %d, hash: %d\n", tid, e_set->opaque, it->keylen, it->hv);
        printf("set at core %ld: id: %ld, item: %ld, keylen: %d, vallen: %d, val: %d\n", tid, e_set->opaque, it, it->keylen, it->vallen, val[0]);
//        uint8_t* key = item_key(it);
//        for(int i=0; i<it->keylen; i++)
//            printf("set id: %ld, key[%d] = %d\n", e_set->opaque, i, key[i]);
        hasht_put(it, NULL);
        item_unref(it);
        send_cq(tid, CQE_TYPE_SRESP, 0, 0, e_set->opaque);
      }
      else if (type == EQE_TYPE_SEGFULL) {
        printf("new segment\n");
        struct segment_header* segment = new_segment(&ia, false);
        if(segment == NULL) {
            printf("Fail to allocate new segment.\n");
            exit(-1);
        }
        send_cq(tid, CQE_TYPE_LOG, get_pointer_offset(segment->data), segment->size, 0);

        // TODO: what to do with full segment?
        eqe_seg_full* e_full = (eqe_seg_full*) e;
        ialloc_nicsegment_full(e_full->last);
      }
      release((q_entry *) e);
      clean_log(&ia, false);
      clean_cq(tid);
      //usleep(10);
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
  settings_init();
  ialloc_init(data_region);

  // spec

  // impl
  hasht_init();
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

  //usleep(100000);
  //maintenance();
  usleep(1000000);

  for(int t=0;t<NUM_THREADS;t++) {
       int rc = pthread_cancel(threads[t]);
       if (rc){
          printf("ERROR; return code from pthread_cancel() is %d\n", rc);
          exit(-1);
       }
  }

  printf("UNMAP memory\n");
  finalize_and_check();
  //ialloc_finalize();

  return 0;
}
