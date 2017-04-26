#include "nic.h"
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
  ialloc_init_slave();

  // spec
  hasht_init();
  spec_run_threads();
  usleep(500000);
  spec_kill_threads();

  // impl
  impl_run_threads();
  usleep(1000000);
  impl_kill_threads();

  // compare
  finalize_and_check();
  ialloc_finalize_slave();
  return 0;
}
