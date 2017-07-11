#include "queue_shared_data1.h"

int main(int argc, char *argv[]) {
  init(argv);
  for(int i=1; i<10; i++)
    push(i, i);

  //usleep(10000);
  while(1);
  finalize_and_check();
}