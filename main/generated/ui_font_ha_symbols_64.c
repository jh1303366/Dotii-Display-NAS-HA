#include "lvgl.h"
static const uint8_t bits[]={0,0,0,0,0,255,255,0,15,255,255,240,15,255,255,240,15,255,255,240,15,255,255,240,15,255,255,240,0,255,255,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,255,255,0,15,255,255,240,15,255,255,240,15,255,255,240,15,255,255,240,15,255,255,240,0,255,255,0,0,0,0,0,0,0,0,15,0,0,0,0,0,15,255,255,255,0,0,0,15,255,255,255,255,0,0,15,255,0,0,15,255,0,15,255,0,0,0,15,255,0,255,0,0,0,0,15,240,15,240,0,0,0,0,255,15,255,0,0,0,0,15,255,15,240,0,0,0,0,255,0,255,0,0,0,0,15,240,15,255,0,0,0,15,255,0,15,255,0,0,15,255,0,0,15,255,255,255,255,0,0,0,15,255,255,255,0,0,0,0,0,15,0,0,0,0};
static const lv_font_fmt_txt_glyph_dsc_t glyphs[]={{.bitmap_index=0,.adv_w=0,.box_w=0,.box_h=0,.ofs_x=0,.ofs_y=0},{.bitmap_index=0,.adv_w=224,.box_w=8,.box_h=33,.ofs_x=0,.ofs_y=7},{.bitmap_index=132,.adv_w=288,.box_w=15,.box_h=15,.ofs_x=0,.ofs_y=31}};
static const lv_font_fmt_txt_cmap_t maps[]={
{.range_start=58,.range_length=1,.glyph_id_start=1,.type=LV_FONT_FMT_TXT_CMAP_FORMAT0_TINY},
{.range_start=176,.range_length=1,.glyph_id_start=2,.type=LV_FONT_FMT_TXT_CMAP_FORMAT0_TINY}};
static const lv_font_fmt_txt_dsc_t dsc={.glyph_bitmap=bits,.glyph_dsc=glyphs,.cmaps=maps,.cmap_num=2,.bpp=4};
const lv_font_t ui_font_ha_symbols_64={.get_glyph_dsc=lv_font_get_glyph_dsc_fmt_txt,.get_glyph_bitmap=lv_font_get_bitmap_fmt_txt,.line_height=48,.base_line=1,.dsc=&dsc,.fallback=&lv_font_montserrat_32};
