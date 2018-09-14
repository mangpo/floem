#include <stdio.h>
#include <stdlib.h>
#include <rte_spinlock.h>
#include <math.h>

#define N_PARAMS 512
#define N_POOLS 100000

typedef struct {
    double ws[N_PARAMS];
    double accums[N_PARAMS];
    rte_spinlock_t lock;
} param_pool;

param_pool params[100000];

double r2()
{
    return (double)rand() / (double)RAND_MAX ;
}

void init_params() {
    int i, j;
    for(i=0; i<N_POOLS; i++) {
        rte_spinlock_init(&params[i].lock);
        for(j=0; j<N_PARAMS; j++) {
            params[i].ws[j] = r2();
            params[i].accums[j] = 0.0;
        }
    }
}

void update_param(uint32_t pool, double param) {
    int j;
    rte_spinlock_lock(&params[pool].lock);
    for(j=0; j<N_PARAMS; j++) {
        params[pool].accums[j] += param * params[pool].ws[j];
	params[pool].accums[j] = sqrt(params[pool].accums[j]);
    }
    rte_spinlock_unlock(&params[pool].lock);
}
