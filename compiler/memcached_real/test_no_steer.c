#include "dpdk.h"
#include "iokvs.h"

void maintenance(struct item_allocator *iallocs)
{
    int i;
    usleep(100000);
    while (1) {
        for (i = 0; i < NUM_THREADS; i++) {
            ialloc_maintenance(&iallocs[i]);
        }
        usleep(10);
    }
}

int main(int argc, char *argv[]) {
  settings_init(argc, argv);
  init(argv);
  //printf("data_region = %p\n", data_region);
  //ialloc_init(data_region);
  hasht_init();
  struct item_allocator *iallocs = get_item_allocators();

  run_threads();
  maintenance(iallocs);
  //while(1) pause();
  return 0;
}
