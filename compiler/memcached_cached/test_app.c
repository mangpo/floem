#include "app.h"
#include "iokvs.h"

int main(int argc, char *argv[]) {
  init(argv);


  int i;
  while(1) {
    for(i=0; i<NUM_THREADS; i++) {
      process_eq(i);
    }
  }
  return 0;
}
