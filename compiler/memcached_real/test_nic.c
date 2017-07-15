#include "dpdk.h"
#include "iokvs.h"

int main(int argc, char *argv[]) {
  settings_init(argc, argv);
  init(argv);
  ialloc_init(data_region);
  run_threads();
  while(1) pause();
  return 0;
}
