#include "varsize_deq.h"

int main(int argc, char *argv[]) {
    init(argv);
    run_threads();
    int i;
    for(i=0; i<64; i++) {
        push(i,i);
    }
    kill_threads();
    return 0;
}