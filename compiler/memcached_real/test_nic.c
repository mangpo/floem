#include "dpdk.h"
#include "iokvs.h"

int main(int argc, char *argv[]) {
  init(argv);
  ialloc_init(data_region);
  run_threads();
  return 0;
}
