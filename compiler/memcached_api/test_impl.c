#include "tmp_impl.h"
#include "iokvs.h"

#define NUM_THREADS     4
typedef eq_entry* (*feq)();
typedef void (*fcq)(cq_entry*);

feq get_eqs[4] = {get_eq0, get_eq1, get_eq2, get_eq3};  // array of pointers to API function get_eq
fcq send_cqs[4] = {send_cq0, send_cq1, send_cq2, send_cq3};  // array of pointers to API function send_eq
//feq get_eqs[1] = {get_eq0};  // array of pointers to API function get_eq
//fcq send_cqs[1] = {send_cq0};  // array of pointers to API function send_eq

static struct item_allocator **iallocs;

void settings_init()
{
    settings.udpport = 11211;
    settings.verbose = 1;
    settings.segsize = 2 * 1024 * 1024;
    settings.segmaxnum = 512;
    settings.segcqsize = 32 * 1024;
}


void run_app(void *threadid) {
  long tid = (long)threadid;

  // init worker
  struct item_allocator ia;
  ialloc_init_allocator(&ia);
  iallocs[tid] = &ia;
  // pass ia->cur to NIC
  cqe_add_logseg* log = (cqe_add_logseg *) malloc(sizeof(cqe_add_logseg));
  log->flags = CQE_TYPE_LOG;
  log->segment = ia.cur;
  send_cqs[tid]((cq_entry*) log);

  printf("Worker %ld starting\n", tid);

  while(true) {
      eq_entry* e = get_eqs[tid]();
      //printf("get_eq %ld\n", e);
      if(e == NULL) {
        //printf("eq_entry at core %ld is null.\n", tid);
      }
      else if (e->flags == EQE_TYPE_RXGET) {

        eqe_rx_get* e_get = (eqe_rx_get*) e;
        item *it = hasht_get(e_get->key, e_get->keylen, e_get->hash);
//        printf("get at core %ld: id: %ld, keylen: %d, hash: %d\n", tid, e_get->opaque, e_get->keylen, e_get->hash);
//        printf("get at core %ld: id: %ld, item = %ld.....\n", tid, e_get->opaque, it);
//        uint8_t* key = e_get->key;
//        for(int i=0; i<e_get->keylen; i++)
//            printf("get id: %ld, key[%d] = %d\n", e_get->opaque, i, key[i]);
        uint8_t* val = item_value(it);
        printf("get at core %ld: id: %ld, keylen: %d, vallen %d, val: %d\n", tid, e_get->opaque, it->keylen, it->vallen, val[0]);
        cqe_send_getresponse* c = (cqe_send_getresponse *) malloc(sizeof(cqe_send_getresponse));
        c->flags = CQE_TYPE_GRESP;
        c->item = it;
        c->opaque = e_get->opaque;
        send_cqs[tid]((cq_entry*) c);
      }
      else if (e->flags == EQE_TYPE_RXSET) {
        eqe_rx_set* e_set = (eqe_rx_set*) e;
        item* it = e_set->item;
        uint8_t * val = item_value(it);
        //printf("set at core %ld: id: %ld, keylen: %d, hash: %d\n", tid, e_set->opaque, it->keylen, it->hv);
        printf("set at core %ld: id: %ld, item: %ld, keylen: %d, vallen: %d, val: %d\n", tid, e_set->opaque, it, it->keylen, it->vallen, val[0]);
//        uint8_t* key = item_key(it);
//        for(int i=0; i<it->keylen; i++)
//            printf("set id: %ld, key[%d] = %d\n", e_set->opaque, i, key[i]);
        hasht_put(it, NULL);
        cqe_send_setresponse* c = (cqe_send_setresponse *) malloc(sizeof(cqe_send_setresponse));
        c->flags = CQE_TYPE_SRESP;
        c->opaque = e_set->opaque;
        send_cqs[tid]((cq_entry*) c);
      }
      usleep(10);
  }
}


int main() {
  settings_init();
  hasht_init();
  //populate_hasht(64);
  ialloc_init();
  iallocs = calloc(NUM_THREADS, sizeof(*iallocs));

  init();

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

  run_threads();

  // TODO: run maintenance();
  usleep(100000);

  for(int t=0;t<NUM_THREADS;t++) {
       int rc = pthread_cancel(threads[t]);
       if (rc){
          printf("ERROR; return code from pthread_cancel() is %d\n", rc);
          exit(-1);
       }
  }
  kill_threads();
  return 0;
}