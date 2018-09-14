#include "app.h"
#include "iokvs.h"
#include <unistd.h>

static struct item_allocator *iallocs;

void run_app(void *threadid) {
  long tid = (long)threadid;
  struct item_allocator* ia = &iallocs[tid];
  printf("Worker %ld: segmaxnum = %ld, ia = %p\n", tid, settings.segmaxnum, ia);
  //ialloc_init_allocator(&ia, tid);
  //iallocs[tid] = &ia;

  printf("Worker %ld starting\n", tid);

  while(true) {
    int i;
    for(i=0; i<NUM_THREADS; i++)
        process_eq(i);
    clean_log(ia, true); // TODO: always true
  }
}

void maintenance()
{
    size_t i;
    usleep(100000);
    while (1) {
        for (i = 0; i < CPU_THREADS; i++) {
            ialloc_maintenance(&iallocs[i]);
        }
        //usleep(10);
    }
}

int main(int argc, char *argv[]) {
  settings_init();
  ialloc_init();
  init(argv);
  hasht_init();
  //iallocs = calloc(NUM_THREADS, sizeof(*iallocs));
  iallocs = get_item_allocators();
  printf("main: segmaxnum = %ld\n", settings.segmaxnum);

  pthread_t threads[CPU_THREADS];
  for(int t=0;t<CPU_THREADS;t++) {
       printf("In main: creating thread %d\n", t);
       int rc = pthread_create(&threads[t], NULL, run_app, (void *)t);
       if (rc){
          printf("ERROR; return code from pthread_create() is %d\n", rc);
          exit(-1);
       }
  }

  printf("Starting maintenance\n");
  maintenance();

  return 0;
}
