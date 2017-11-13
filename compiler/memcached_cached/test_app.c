#include "app.h"
#include "iokvs.h"

int main(int argc, char *argv[]) {
  int i;
  for(i=0; i<NUM_THREADS; i++) {
    process_eq(i);
  }
  return 0;
}
