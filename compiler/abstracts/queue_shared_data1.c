#include "queue_shared_data1.h"

int main() {
  init();
  for(int i=1; i<10; i++)
    push(i, i);

  usleep(10000);
  finalize_and_check();
}