#include "app.h"
#include "iokvs.h"

#define NUM_THREADS     10

static struct item_allocator **iallocs;

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
  printf("Worker %ld: segmaxnum = %d\n", tid, settings.segmaxnum);
  struct item_allocator ia;
  ialloc_init_allocator(&ia);
  iallocs[tid] = &ia;
  init_segment(tid, &ia);

  printf("Worker %ld starting\n", tid);

  while(true) {
    //printf(".");
    process_eq(tid);
    clean_log(&ia, true); // TODO: is this frequent enough?
    bool cleaning = true;
    while(cleaning) { cleaning = clean_cq(tid); }  // TODO: clean before process_eq
  }
}

void maintenance()
{
    size_t i;
    usleep(100000);
    while (1) {
        for (i = 0; i < NUM_THREADS; i++) {
            ialloc_maintenance(iallocs[i]);
        }
        usleep(10);
    }
}

int main(int argc, char *argv[]) {
  settings_init(argc, argv);
  init(argv);
  ialloc_init(data_region);
  hasht_init();
  iallocs = calloc(NUM_THREADS, sizeof(*iallocs));
  printf("main: segmaxnum = %d\n", settings.segmaxnum);

  pthread_t threads[NUM_THREADS];
  for(int t=0;t<NUM_THREADS;t++) {
       printf("In main: creating thread %d\n", t);
       int rc = pthread_create(&threads[t], NULL, run_app, (void *)t);
       if (rc){
          printf("ERROR; return code from pthread_create() is %d\n", rc);
          exit(-1);
       }
  }

  printf("Starting maintenance\n");
  maintenance();
  //while(1);

  return 0;
}
