#include "tmp_impl.h"
#include "iokvs.h"

#define NUM_THREADS     4
typedef eq_entry* (*feq)();
typedef void (*fcq)(cq_entry*);

feq get_eqs[4] = {get_eq0, get_eq1, get_eq2, get_eq3};  // array of pointers to API function get_eq
fcq send_cqs[4] = {send_cq0, send_cq1, send_cq2, send_cq3};  // array of pointers to API function send_eq

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

  printf("Worker starting\n");

  while(true) {
      eq_entry* e = get_eqs[tid]();
      if(e == NULL) {
        printf("eq_entry at core %ld is null.\n", tid);
      }
      else if (e->flags == EQE_TYPE_RXGET) {

        eqe_rx_get* e_get = (eqe_rx_get*) e;
        printf("eq_entry at core %ld: OPAQUE: %ld, len: %d\n", tid, e_get->opaque, e_get->keylen);
        item *it = hasht_get(e_get->key, e_get->keylen, e_get->hash);
        cqe_send_getresponse* c = (cqe_send_getresponse *) malloc(sizeof(cqe_send_getresponse));
        c->item = it;
        c->opaque = e_get->opaque;
        send_cqs[tid]((cq_entry*) c);
      }
    usleep(10);
  }
}


int main() {
  settings_init();
  populate_hasht(64);
  ialloc_init();
  iallocs = calloc(NUM_THREADS, sizeof(*iallocs));

  init();
  run_threads();

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

  // TODO: run maintenance();
  usleep(500);

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