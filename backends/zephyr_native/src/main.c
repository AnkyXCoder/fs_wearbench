/*
 * Zephyr native_sim wear profiler.
 *
 * Currently supports NVS. ZMS and LittleFS can be added under the same
 * WEAR_BACKEND_* guards.
 */

#include "workload.h"

#include <stdio.h>
#include <stdint.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/drivers/flash.h>
#include <zephyr/drivers/flash/flash_simulator.h>
#include <zephyr/storage/flash_map.h>
#include <zephyr/stats/stats.h>
#include <zephyr/sys/util.h>
#include <posix_board_if.h>

#if WEAR_BACKEND_NVS
#include <zephyr/kvss/nvs.h>
#elif WEAR_BACKEND_ZMS
#include <zephyr/kvss/zms.h>
#elif WEAR_BACKEND_LITTLEFS
#include <zephyr/fs/fs.h>
#include <zephyr/fs/littlefs.h>
#include <zephyr/storage/flash_map.h>
#else
#error "No backend selected"
#endif

#define WEAR_PARTITION wear_storage

#define MAX_ERASE_UNITS 512

static uint32_t erase_cycles[MAX_ERASE_UNITS];
static off_t g_part_offset;
static size_t g_part_size;
static size_t g_sector_size;

static int wear_erase_callback(const struct device *dev, off_t offset)
{
    const struct flash_simulator_params *params = flash_simulator_get_params(dev);
    size_t flash_size;
    uint8_t *mock = flash_simulator_get_memory(dev, &flash_size);

    if (offset < g_part_offset || (size_t)(offset - g_part_offset) >= g_part_size) {
        return 0;
    }

    uint32_t unit = (uint32_t)((offset - g_part_offset) / g_sector_size);
    if (unit < MAX_ERASE_UNITS) {
        erase_cycles[unit]++;
    }

    if (mock != NULL) {
        memset(mock + offset, params->erase_value, params->erase_unit);
    }

    return 0;
}

static struct flash_simulator_cb wear_cbs = {
    .erase_unit = wear_erase_callback,
};

static int find_stat(struct stats_hdr *hdr, void *arg, const char *name, uint16_t off)
{
    struct {
        const char *name;
        uint32_t **ptr;
    } *target = arg;

    if (!strcmp(name, target->name)) {
        *target->ptr = (uint32_t *)((uint8_t *)hdr + off);
    }

    return 0;
}

static uint32_t get_stat(const char *group, const char *name)
{
    uint32_t *ptr = NULL;
    struct stats_hdr *hdr = stats_group_find(group);

    if (hdr == NULL) {
        return 0;
    }

    struct {
        const char *name;
        uint32_t **ptr;
    } target = {name, &ptr};

    stats_walk(hdr, find_stat, &target);

    return ptr ? *ptr : 0;
}

int main(void)
{
    int rc;
    uint32_t i;
    uint32_t user_bytes = WEAR_RECORD_COUNT * WEAR_RECORD_SIZE;

    const struct device *flash_dev = PARTITION_DEVICE(WEAR_PARTITION);
    if (!device_is_ready(flash_dev)) {
        printf("Flash device not ready\n");
        return 0;
    }

    off_t offset = PARTITION_OFFSET(WEAR_PARTITION);
    size_t part_size = PARTITION_SIZE(WEAR_PARTITION);

    struct flash_pages_info info;
    rc = flash_get_page_info_by_offs(flash_dev, offset, &info);
    if (rc) {
        printf("flash_get_page_info_by_offs failed: %d\n", rc);
        return 0;
    }

    g_part_offset = info.start_offset;
    g_part_size = part_size;
    g_sector_size = info.size;

    flash_simulator_set_callbacks(flash_dev, &wear_cbs);

    uint8_t record[WEAR_RECORD_SIZE];
    memset(record, 0xA5, WEAR_RECORD_SIZE);

    const char *backend_name = NULL;
    uint32_t sector_count = 0;

#if WEAR_BACKEND_NVS
    struct nvs_fs fs = {0};

    fs.flash_device = flash_dev;
    fs.offset = info.start_offset;
    fs.sector_size = info.size;
    fs.sector_count = part_size / info.size;
    sector_count = fs.sector_count;
    backend_name = "nvs";

    rc = nvs_mount(&fs);
    if (rc) {
        printf("nvs_mount failed: %d\n", rc);
        return 0;
    }

    for (i = 0; i < WEAR_RECORD_COUNT; i++) {
        record[0] = (uint8_t)(i & 0xFF);
        ssize_t written = nvs_write(&fs, 1, record, WEAR_RECORD_SIZE);
        if (written != (ssize_t)WEAR_RECORD_SIZE) {
            printf("nvs_write failed at record %u: %d\n", i, (int)written);
            return 0;
        }
    }
#elif WEAR_BACKEND_ZMS
    struct zms_fs fs = {0};

    fs.flash_device = flash_dev;
    fs.offset = info.start_offset;
    fs.sector_size = info.size;
    fs.sector_count = part_size / info.size;
    sector_count = fs.sector_count;
    backend_name = "zms";

    rc = zms_mount(&fs);
    if (rc) {
        printf("zms_mount failed: %d\n", rc);
        return 0;
    }

    for (i = 0; i < WEAR_RECORD_COUNT; i++) {
        record[0] = (uint8_t)(i & 0xFF);
        ssize_t written = zms_write(&fs, 1, record, WEAR_RECORD_SIZE);
        if (written != (ssize_t)WEAR_RECORD_SIZE) {
            printf("zms_write failed at record %u: %d\n", i, (int)written);
            return 0;
        }
    }
#elif WEAR_BACKEND_LITTLEFS
    FS_LITTLEFS_DECLARE_DEFAULT_CONFIG(storage);
    static struct fs_mount_t lfs_mnt = {
        .type = FS_LITTLEFS,
        .fs_data = &storage,
        .storage_dev = (void *)PARTITION_ID(wear_storage),
        .mnt_point = "/lfs",
    };

    sector_count = part_size / g_sector_size;
    backend_name = "zephyr_littlefs";

    storage.cfg.block_size = g_sector_size;
    storage.cfg.block_count = sector_count;

    rc = fs_mount(&lfs_mnt);
    if (rc) {
        printf("fs_mount failed: %d\n", rc);
        return 0;
    }

    struct fs_file_t file;
    fs_file_t_init(&file);

    rc = fs_open(&file, "/lfs/sensor.log", FS_O_CREATE | FS_O_WRITE | FS_O_APPEND);
    if (rc) {
        printf("fs_open failed: %d\n", rc);
        return 0;
    }

    for (i = 0; i < WEAR_RECORD_COUNT; i++) {
        record[0] = (uint8_t)(i & 0xFF);
        ssize_t written = fs_write(&file, record, WEAR_RECORD_SIZE);
        if (written != (ssize_t)WEAR_RECORD_SIZE) {
            printf("fs_write failed at record %u: %d\n", i, (int)written);
            return 0;
        }
    }

    rc = fs_close(&file);
    if (rc) {
        printf("fs_close failed: %d\n", rc);
        return 0;
    }

    rc = fs_unmount(&lfs_mnt);
    if (rc) {
        printf("fs_unmount failed: %d\n", rc);
        return 0;
    }
#endif

    uint32_t bytes_read = get_stat("flash_sim_stats", "bytes_read");
    uint32_t bytes_written = get_stat("flash_sim_stats", "bytes_written");

    uint32_t erased_units = 0;
    for (i = 0; i < sector_count; i++) {
        if (erase_cycles[i]) {
            erased_units += erase_cycles[i];
        }
    }
    uint32_t erased_bytes = erased_units * g_sector_size;

    printf("{\n");
    printf("  \"backend\": \"%s\",\n", backend_name);
    printf("  \"config\": {\n");
    printf("    \"record_size\": %u,\n", WEAR_RECORD_SIZE);
    printf("    \"record_count\": %u,\n", WEAR_RECORD_COUNT);
    printf("    \"block_size\": %u,\n", (unsigned)g_sector_size);
    printf("    \"block_count\": %u\n", (unsigned)sector_count);
    printf("  },\n");
    printf("  \"metrics\": {\n");
    printf("    \"user_bytes\": %u,\n", user_bytes);
    printf("    \"readed_bytes\": %u,\n", bytes_read);
    printf("    \"proged_bytes\": %u,\n", bytes_written);
    printf("    \"erased_bytes\": %u\n", erased_bytes);
    printf("  },\n");
    printf("  \"per_block_wear\": [\n");

    int first = 1;
    for (i = 0; i < sector_count; i++) {
        if (erase_cycles[i] == 0) {
            continue;
        }
        printf("%s\n    {\"block\": %u, \"cycles\": %u}", first ? "" : ",", i, erase_cycles[i]);
        first = 0;
    }
    printf("\n  ]\n");
    printf("}\n");

    posix_exit(0);
}
