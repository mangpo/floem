#include "queue_shared_data2.h"

int main(int argc, char *argv[]) {
  init(argv);
  usleep(1000);
//  for(int i=0; i<10; i++)
//    pop(0);
  run_threads();
  while(1);

  finalize_and_check();
}