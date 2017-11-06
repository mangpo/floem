#include "dpdk.h"
#include "protocol_binary.h"

int main(int argc, char *argv[]) {
  printf("sizeof(param_message) = %d\n", sizeof(param_message));
    init(argv);
    init_params();

    run_threads();
    while(1) pause();
    kill_threads();
}
