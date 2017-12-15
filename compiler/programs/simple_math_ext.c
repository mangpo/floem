#include "simple_math.h"

int main(int argc, char *argv[]) {
    init(argv);    // does nothing in this program
    // extra init between here
    run_threads(); // does nothing in this program
    int x = inc2(42);
    printf("%d\n", x);
    return 0;
}