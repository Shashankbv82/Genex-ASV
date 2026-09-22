#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/gpio.h>
#include <time.h>

typedef struct {
    uint64_t t;
    int lvl;
} Edge;

static Edge edge_buf[2048];
static int edge_count = 0;
static uint64_t last_edge_t = 0;

static inline int get_lvl(uint64_t t) {
    int low = 0, high = edge_count - 1;
    int ans = -1;
    while (low <= high) {
        int mid = (low + high) / 2;
        if (edge_buf[mid].t <= t) {
            ans = mid;
            low = mid + 1;
        } else {
            high = mid - 1;
        }
    }
    return (ans >= 0) ? edge_buf[ans].lvl : 1;
}

static int try_decode(double bit_ns, double phase, uint8_t *out) {
    int idx = 0;
    while (idx < edge_count && edge_buf[idx].lvl != 0) idx++;
    if (idx >= edge_count - 5) return 0;

    uint64_t t_cur = edge_buf[idx].t;

    for (int b = 0; b < 32; b++) {
        uint8_t val = 0;
        for (int bit = 0; bit < 8; bit++) {
            uint64_t st = t_cur + (uint64_t)((phase + bit) * bit_ns);
            if (get_lvl(st)) {
                val |= (1 << bit);
            }
        }
        if (b == 0 && val != 0x20) return 0;
        if (b == 1 && val != 0x40) return 0;
        out[b] = val;

        if (b < 31) {
            uint64_t min_fall = t_cur + (uint64_t)(9.6 * bit_ns);
            uint64_t max_fall = t_cur + (uint64_t)(13.5 * bit_ns);
            uint64_t next_fall = 0;
            int next_idx = idx;
            for (int p = idx; p < edge_count; p++) {
                if (edge_buf[p].t >= min_fall) {
                    if (edge_buf[p].t > max_fall) break;
                    if (edge_buf[p].lvl == 0) {
                        next_fall = edge_buf[p].t;
                        next_idx = p;
                        break;
                    }
                }
            }
            if (next_fall > 0) {
                t_cur = next_fall;
                idx = next_idx;
            } else {
                t_cur += (uint64_t)(11.0 * bit_ns);
            }
        }
    }

    uint16_t sum = 0;
    for (int i = 0; i < 30; i++) sum += out[i];
    uint16_t chk = 0xFFFF - sum;
    uint16_t fchk = out[30] | ((uint16_t)out[31] << 8);

    return (chk == fchk);
}

static int decode_frame(uint8_t *out) {
    if (edge_count < 30) return 0;
    static const double bauds[] = { 8680.555, 8715.0, 8645.0, 8600.0, 8760.0, 8550.0, 8800.0 };
    static const double phases[] = { 1.5, 1.4, 1.6, 1.3, 1.7 };
    for (int b = 0; b < 7; b++) {
        for (int p = 0; p < 5; p++) {
            if (try_decode(bauds[b], phases[p], out)) return 1;
        }
    }
    return 0;
}

int main(int argc, char **argv) {
    int pin = 22;
    if (argc > 1) pin = atoi(argv[1]);

    int chip_fd = open("/dev/gpiochip0", O_RDWR);
    if (chip_fd < 0) {
        perror("open /dev/gpiochip0");
        return 1;
    }

    struct gpio_v2_line_request req;
    memset(&req, 0, sizeof(req));
    req.offsets[0] = pin;
    req.num_lines = 1;
    req.config.flags = GPIO_V2_LINE_FLAG_INPUT | GPIO_V2_LINE_FLAG_EDGE_RISING | GPIO_V2_LINE_FLAG_EDGE_FALLING;
    strncpy(req.consumer, "genex_ibus", sizeof(req.consumer) - 1);

    if (ioctl(chip_fd, GPIO_V2_GET_LINE_IOCTL, &req) < 0) {
        perror("GPIO_V2_GET_LINE_IOCTL");
        close(chip_fd);
        return 2;
    }
    close(chip_fd);

    int line_fd = req.fd;
    struct gpio_v2_line_event events[64];
    uint8_t frame[32];

    while (1) {
        int n = read(line_fd, events, sizeof(events));
        if (n <= 0) {
            if (n < 0) perror("read events");
            break;
        }
        int num_events = n / (int)sizeof(struct gpio_v2_line_event);
        for (int i = 0; i < num_events; i++) {
            uint64_t t = events[i].timestamp_ns;
            int lvl = (events[i].id == GPIO_V2_LINE_EVENT_RISING_EDGE) ? 1 : 0;

            if (last_edge_t > 0) {
                uint64_t gap = t - last_edge_t;
                if (gap >= 1200000ULL) {
                    if (decode_frame(frame)) {
                        ssize_t w = write(STDOUT_FILENO, frame, 32);
                        (void)w;
                    }
                    edge_count = 0;
                }
            }
            last_edge_t = t;
            if (edge_count < 2048) {
                edge_buf[edge_count].t = t;
                edge_buf[edge_count].lvl = lvl;
                edge_count++;
            }
        }
    }

    close(line_fd);
    return 0;
}
