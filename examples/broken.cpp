#include <vector>
#include <map>
#include <cstring>
#include <string>

// --- Error 1: vector of references (template instantiation error) ---
template<typename T>
void process(const std::vector<T>& items) {
    std::vector<int&> refs;          // ERROR: cannot form pointer to reference
    for (auto& item : items) {
        refs.push_back(item);
    }
}

// --- Error 2: taking address of vector<bool> proxy reference ---
void deep_thought(std::vector<int>& v) {
    std::vector<bool> flags = {true, false, true};
    bool* ptr = &flags[0];           // ERROR: vector<bool>::reference is an rvalue
    if (ptr) {
        v.push_back(42);
    }
}

// --- Warning 1: returning reference to local ---
const auto& get_dangling() {
    int local = 99;
    return local;                    // WARNING: reference to local variable
}

// --- Error 3: constexpr OOB access ---
constexpr int peek() {
    int nums[] = {10, 20, 30};
    return nums[5];                  // ERROR: array subscript out of bounds
}

// --- Error 4: mixing new/free + strcpy type mismatch ---
void raw_memory(int* p) {
    int* q = new int(42);
    free(q);                         // ERROR: free not declared (<cstdlib>)
    (void)p;
}

// --- Error 5: missing <algorithm> ---
class Processor {
public:
    void run();
};

void Processor::run() {
    std::vector<int> values = {3, 1, 4, 1, 5, 9};
    std::sort(values.begin(), values.end());   // ERROR: sort not in <algorithm>
}

// --- Warning 2: unused parameter ---
int unused_param(int x, int y) {
    return x;                        // WARNING: unused parameter 'y'
}

int main() {
    Processor p;
    p.run();
    return 0;
}
