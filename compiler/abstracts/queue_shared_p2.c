#include "queue_shared_p2.h"

int main() {
  init();
  usleep(1000);
  for(int i=0; i<10; i++)
    pop(0);

  finalize_and_check();
}