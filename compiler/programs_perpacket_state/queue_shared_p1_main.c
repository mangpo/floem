#include "queue_shared_p1.h"
#include <unistd.h>

int main(int argc, char *argv[]) {
  init(argv);
  int* p = data_region;
  for(int i=0; i<10; i++)
    p[i] = i;

  for(int i=0; i<10; i++)
    push(i);

  usleep(10000);
  finalize_and_check();
}