#include "nic.h"
#include "iokvs.h"

#define NUM_THREADS     4

static struct item_allocator **iallocs;

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

int main(int argc, char *argv[]) {
  init(argv);
  ialloc_init(data_region);

  // spec
  hasht_init();
  spec_run_threads();
  usleep(500000);
  spec_kill_threads();

  // impl
  printf("------------------ impl --------------------\n");
  impl_run_threads();
  //run_threads();
  usleep(1000000);
  impl_kill_threads();
  //kill_threads();

  // compare
  finalize_and_check();
  //ialloc_finalize_slave();
  return 0;
}
