#include "app.h"
#include "iokvs.h"
#include <unistd.h>

static struct item_allocator **iallocs;

void run_app(void *threadid) {
  long tid = (long)threadid;
  printf("Worker %ld: segmaxnum = %ld\n", tid, settings.segmaxnum);
  struct item_allocator ia;
  ialloc_init_allocator(&ia, tid);
  iallocs[tid] = &ia;
  init_segment(tid, &ia);
  init_segment(tid, &ia);
  init_segment(tid, &ia);
  init_segment(tid, &ia);

  printf("Worker %ld starting\n", tid);

  int round = 0;
  int qid = 0;
  while(true) {
    process_eq(qid);
    clean_log(&ia, true); // TODO: is this frequent enough?
    qid = (qid + 1) % 3;
  }
}

void maintenance()
{
    size_t i;
    usleep(100000);
    while (1) {
        create_segment();
        for (i = 0; i < NUM_THREADS; i++) {
            ialloc_maintenance(iallocs[i]);
        }
        //usleep(10);
    }
}

int main(int argc, char *argv[]) {
  //settings_init(argv);
  init(argv);
  ialloc_init();
  hasht_init();
  iallocs = calloc(NUM_THREADS, sizeof(*iallocs));
  printf("main: segmaxnum = %ld\n", settings.segmaxnum);

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
