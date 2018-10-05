# Library of C Functions

This documentation describes utilitly functions that can be used in C implemention of an element.

1. [Locks](#Locks)
2. [Atomic Instructions](#Atomic-Instructions)
3. [Byte Order Conversion](#Byte-Order-Conversion)
4. [Memory Allocation](#Memory-Allocation)
5. [Timing](#Timing)

<a name="Locks"></a>
## 1. Locks
`spinlock_t`: spin lock type
```c
void spinlock_init(spinlock_t *lock)
void spinlock_lock(spinlock_t *lock)
void spinlock_unlock(spinlock_t *lock)
```

<a name="Atomic-Instructions"></a>
These are macros for GCC atomic instructions and Cavium atomic instructions.
## 2. Atomic Instructions
```c
int32_t __sync_fetch_and_add32(int32_t *ptr, int32_t inc)
int64_t __sync_fetch_and_add64(int64_t *ptr, int64_t inc)
int32_t __sync_fetch_and_sub32(int32_t *ptr, int32_t sub)
int64_t __sync_fetch_and_sub64(int64_t *ptr, int64_t sub)
uint32_t  __sync_bool_compare_and_swap32(uint32_t *ptr, uint32_t old_val, uint32_t new_val)
uint64_t  __sync_bool_compare_and_swap64(uint64_t *ptr, uint64_t old_val, uint64_t new_val)
```

This command issues a full memory barrier.
```c
__SYNC;
```

<a name="Byte-Order-Conversion"></a>
## 3. Byte Order Conversion
These functions reverse the byte order when running on a CPU. They are identify functions when running on a NIC.
```c
uint16_t htons(uint16_t x)
uint32_t htonl(uint32_t x)
uint64_t htonp(uint64_t x)
```

These functions reverse the byte order when running on a NIC. They are identify functions when running on a CPU.
```c
uint16_t nic_htons(uint16_t x)
uint32_t nic_htonl(uint32_t x)
uint64_t nic_htonp(uint64_t x)
```

<a name="Memory-Allocation"></a>
## 4. Memory Allocation
On a Cavium LiquidiO NIC, `malloc` and `free` are for allocating and deallocating memory local to a core. To allocate a memory that shared between LiquidIO core, users must use the following fucntions.
```c
void* shared_mm_malloc(int size);
void  shared_mm_free(void *ptr);
```

<a name="Timing"></a>
## 5. Timing
On a Cavium LiquidiO NIC only.
```c
uint64_t core_time_now_ns();  // nanoseconds computed from cycle count.
uint64_t core_time_now_us();  // microseconds computed from cycle count.
```
