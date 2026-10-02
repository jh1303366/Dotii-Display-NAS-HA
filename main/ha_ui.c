#include "ha_ui.h"
#include "connectivity.h"
#include "ha_reference_art.h"
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <math.h>
#include <stdlib.h>
LV_FONT_DECLARE(ui_font_detail_20);
LV_FONT_DECLARE(ui_font_digits_64);
LV_FONT_DECLARE(ui_font_ha_symbols_64);
LV_FONT_DECLARE(ui_font_ha_numbers_80);
LV_FONT_DECLARE(ui_font_ha_numbers_80);
#define BLUE 0x69C9FF
#define CYAN 0x63DCFA
#define TEXT 0xF6FAFF
#define MUTED 0x9DACBD
#define TRACK 0x202B39
static lv_obj_t *s_screen,*s_pane,*s_clock,*s_footer;
static const codex_snapshot_t *s_data;
static bool (*s_touch_allowed)(void);
static int s_page,s_selected=-1,s_list_page;
static bool s_select_mode,s_ignore_click,s_dirty;
static lv_font_t s_large_font;
static uint32_t s_pending,s_pending_seq,s_revision,s_hash;
static const char *mode_text(const char *mode){
 if(!strcmp(mode,"off"))return "关机";
 if(!strcmp(mode,"cool"))return "制冷";
 if(!strcmp(mode,"heat"))return "制热";
 if(!strcmp(mode,"auto"))return "自动";
 if(!strcmp(mode,"dry"))return "除湿";
 if(!strcmp(mode,"fan_only"))return "送风";
 if(!strcmp(mode,"heat_cool"))return "冷热";
 return mode;
}
static bool connected(void){return s_data&&s_data->ha_enabled&&s_data->ha_connected&&s_data->ha_updated_at>0&&time(NULL)-s_data->ha_updated_at<=30&&connectivity_is_wifi_connected();}
static bool blocked(const ha_entity_t*e){return !connected()||s_pending||!e||!e->available;}
static int role(const char*r){if(s_data)for(int i=0;i<s_data->ha_entity_count;i++)if(!strcmp(s_data->ha_entities[i].role,r))return i;return -1;}
static int domain(const char*d,int n){if(s_data)for(int i=0;i<s_data->ha_entity_count;i++)if(!strcmp(s_data->ha_entities[i].domain,d)&&n--==0)return i;return -1;}
static int count(const char*d){int n=0;while(domain(d,n)>=0)n++;return n;}
static const ha_entity_t *entity(int slot){return s_data&&slot>=0&&slot<s_data->ha_entity_count?&s_data->ha_entities[slot]:NULL;}
static void build(void);
static lv_obj_t *box(lv_obj_t*p,int x,int y,int w,int h,uint32_t bg,int radius){lv_obj_t*o=lv_obj_create(p);lv_obj_remove_style_all(o);lv_obj_set_pos(o,x,y);lv_obj_set_size(o,w,h);lv_obj_set_style_bg_color(o,lv_color_hex(bg),0);lv_obj_set_style_bg_opa(o,LV_OPA_COVER,0);lv_obj_set_style_radius(o,radius,0);lv_obj_remove_flag(o,LV_OBJ_FLAG_SCROLLABLE);lv_obj_remove_flag(o,LV_OBJ_FLAG_CLICKABLE);lv_obj_add_flag(o,LV_OBJ_FLAG_EVENT_BUBBLE);return o;}
static lv_obj_t *label(lv_obj_t*p,const char*t,int x,int y,int w,uint32_t c){lv_obj_t*o=lv_label_create(p);lv_obj_set_style_text_font(o,&ui_font_detail_20,0);lv_obj_set_style_text_color(o,lv_color_hex(c),0);lv_label_set_text(o,t);lv_obj_set_pos(o,x,y);lv_obj_set_width(o,w);lv_obj_set_style_text_align(o,LV_TEXT_ALIGN_CENTER,0);lv_label_set_long_mode(o,LV_LABEL_LONG_DOT);return o;}
static lv_obj_t *big(const char*t,int x,int y,int w){lv_obj_t*o=label(s_pane,t,x,y,w,TEXT);lv_obj_set_style_text_font(o,&s_large_font,0);return o;}
static void disabled(lv_obj_t*o,bool v){if(v)lv_obj_add_state(o,LV_STATE_DISABLED);else lv_obj_remove_state(o,LV_STATE_DISABLED);}
static void send_action(const char*a,const char*v){const ha_entity_t*e=entity(s_selected);if(blocked(e)||!e->controllable)return;if(connectivity_ha_command(s_selected,s_data->ha_revision,a,v)){s_pending=lv_tick_get();s_pending_seq=s_data->ha_result_seq;}s_dirty=true;}
static void event(lv_event_t*ev){
 lv_event_code_t code=lv_event_get_code(ev);if(code==LV_EVENT_PRESSED)s_ignore_click=s_touch_allowed&&!s_touch_allowed();
 if(code!=LV_EVENT_CLICKED||s_ignore_click||(s_touch_allowed&&!s_touch_allowed()))return;
 intptr_t a=(intptr_t)lv_event_get_user_data(ev);
 if(a==100){ha_ui_back();return;}if(a==101||a==102){ha_ui_page(a==101?-1:1);return;}
 if(a>=1000&&a<1008){s_page=a-1000;s_selected=-1;s_select_mode=false;s_list_page=0;build();return;}
 if(a==110||a==111){s_list_page+=a==110?-1:1;if(s_list_page<0)s_list_page=0;build();return;}
 if(a>=2000&&a<2000+HA_ENTITY_MAX){s_selected=a-2000;s_select_mode=false;build();return;}
 if(a==120||a==121){const ha_entity_t*e=entity(s_selected);if(!e)return;int n=count(e->domain);for(int i=0;i<n;i++)if(domain(e->domain,i)==s_selected){s_selected=domain(e->domain,(i+n+(a==120?-1:1))%n);break;}s_select_mode=false;build();return;}
 const ha_entity_t*e=entity(s_selected);if(blocked(e))return;char value[24];
 if(a==200&&(!strcmp(e->domain,"climate")?e->mode_count>0:e->controllable))send_action(!strcmp(e->domain,"climate")?"mode":!strcmp(e->state,"off")?"turn_on":"turn_off",!strcmp(e->domain,"climate")?"off":"");
 if(a==201||a==202){float target=e->temperature+(a==201?-1:1)*e->temp_step;if(target>=e->min_temp&&target<=e->max_temp){snprintf(value,sizeof(value),"%.1f",(double)target);send_action("temperature",value);}}
 if(a==203){s_select_mode=true;build();return;}
 if(a>=300&&a<300+e->mode_count){s_select_mode=false;send_action("mode",e->modes[a-300]);}
 if(a==204||a==205){int v=(int)lroundf(!strcmp(e->domain,"light")?fmaxf(e->brightness,0)*100/255:fmaxf(e->percentage,0));v+=(a==204?-10:10);if(v<0)v=0;if(v>100)v=100;snprintf(value,sizeof(value),"%d",v);send_action(!strcmp(e->domain,"light")?"brightness":"percentage",value);}
 if(a>=400&&a<=403&&(e->vacuum_actions&(1<<(a-400)))){const char*act[]={"start","pause","stop","return_to_base"};send_action(act[a-400],"");}
 build();
}
static lv_obj_t *button(lv_obj_t*p,const char*t,int x,int y,int w,int h,int a,bool off){
 lv_obj_t*o=lv_button_create(p);lv_obj_remove_style_all(o);lv_obj_set_pos(o,x,y);lv_obj_set_size(o,w,h);lv_obj_set_style_radius(o,h/2,0);lv_obj_set_style_bg_color(o,lv_color_hex(0x243848),0);lv_obj_set_style_bg_grad_color(o,lv_color_hex(0x122330),0);lv_obj_set_style_bg_grad_dir(o,LV_GRAD_DIR_VER,0);lv_obj_set_style_bg_opa(o,LV_OPA_COVER,0);lv_obj_set_style_border_color(o,lv_color_hex(0x476477),0);lv_obj_set_style_border_width(o,1,0);lv_obj_set_style_bg_color(o,lv_color_hex(0x3176A8),LV_STATE_PRESSED);lv_obj_set_style_opa(o,LV_OPA_40,LV_STATE_DISABLED);lv_obj_remove_flag(o,LV_OBJ_FLAG_SCROLLABLE);lv_obj_add_flag(o,LV_OBJ_FLAG_EVENT_BUBBLE);disabled(o,off);lv_obj_t*l=label(o,t,0,0,w,BLUE);lv_obj_set_style_text_font(l,&ui_font_detail_20,0);if(strlen(t)<=3)lv_obj_set_style_text_font(l,&lv_font_montserrat_32,0);lv_obj_center(l);lv_obj_add_event_cb(o,event,LV_EVENT_ALL,(void*)(intptr_t)a);return o;
}
static lv_obj_t *arc(int x,int y,int size,int start,int end,int value,uint32_t c,int width){lv_obj_t*a=lv_arc_create(s_pane);lv_obj_remove_style_all(a);lv_obj_set_pos(a,x,y);lv_obj_set_size(a,size,size);lv_arc_set_rotation(a,0);lv_arc_set_bg_angles(a,start,end);lv_arc_set_range(a,0,100);lv_arc_set_value(a,value);lv_obj_set_style_arc_color(a,lv_color_hex(TRACK),LV_PART_MAIN);lv_obj_set_style_arc_width(a,width,LV_PART_MAIN);lv_obj_set_style_arc_rounded(a,true,LV_PART_MAIN);lv_obj_set_style_arc_color(a,lv_color_hex(c),LV_PART_INDICATOR);lv_obj_set_style_arc_width(a,width,LV_PART_INDICATOR);lv_obj_set_style_arc_rounded(a,true,LV_PART_INDICATOR);lv_obj_remove_flag(a,LV_OBJ_FLAG_CLICKABLE);
 lv_obj_set_style_arc_opa(a,LV_OPA_TRANSP,LV_PART_INDICATOR);
 int span=(end-start+360)%360;if(value<0){value=0;}if(value>100){value=100;}int filled=span*value/100;
 const uint32_t from=c==CYAN?0x3ED5F6:0x438FFF,to=c==CYAN?0x7FE6FF:0xBAE8FF;
 for(int part=0;part<48;part++){int begin=filled*part/48,finish=filled*(part+1)/48;if(finish<=begin)continue;uint32_t shade=0;for(int shift=0;shift<=16;shift+=8){int lo=(from>>shift)&255,hi=(to>>shift)&255;shade|=(uint32_t)(lo+(hi-lo)*part/47)<<shift;}
  lv_obj_t*seg=lv_arc_create(s_pane);lv_obj_remove_style_all(seg);lv_obj_set_pos(seg,x,y);lv_obj_set_size(seg,size,size);lv_arc_set_bg_angles(seg,(start+begin+(part?-1:0)+360)%360,(start+finish+(part<47?1:0))%360);lv_arc_set_value(seg,100);lv_obj_set_style_arc_opa(seg,LV_OPA_TRANSP,LV_PART_MAIN);lv_obj_set_style_arc_color(seg,lv_color_hex(shade),LV_PART_INDICATOR);lv_obj_set_style_arc_width(seg,width,LV_PART_INDICATOR);lv_obj_set_style_arc_rounded(seg,part==0||part==47,LV_PART_INDICATOR);lv_obj_remove_flag(seg,LV_OBJ_FLAG_CLICKABLE);
 }
 return a;}
static void outer(int a,int b,int c){arc(15,15,436,190,255,a,BLUE,14);arc(15,15,436,105,175,b,0x4C91FF,14);arc(15,15,436,285,75,c,CYAN,14);}
static void icon(const char*t,int x,int y,int w,uint32_t c){lv_obj_t*l=label(s_pane,t,x,y,w,c);lv_obj_set_style_text_font(l,&lv_font_montserrat_32,0);}
static void art(const lv_image_dsc_t*src,int x,int y){lv_obj_t*i=lv_image_create(s_pane);lv_image_set_src(i,src);lv_obj_set_pos(i,x,y);lv_obj_remove_flag(i,LV_OBJ_FLAG_CLICKABLE);}
static __attribute__((unused)) void bulb(int x,int y){lv_obj_t*b=box(s_pane,x,y,32,36,0,16);lv_obj_set_style_border_color(b,lv_color_hex(BLUE),0);lv_obj_set_style_border_width(b,3,0);box(s_pane,x+8,y+30,16,9,BLUE,3);box(s_pane,x+10,y+40,12,4,BLUE,2);}
static void top(const char*t){label(s_pane,t,106,46,254,TEXT);button(s_pane,LV_SYMBOL_LEFT,69,45,44,44,100,false);}
static void nav(void){button(s_pane,LV_SYMBOL_LEFT,107,359,48,48,101,false);button(s_pane,LV_SYMBOL_RIGHT,311,359,48,48,102,false);char t[20];snprintf(t,sizeof(t),"%d / 8",s_page+1);label(s_pane,t,171,369,124,MUTED);}
static void state_value(int slot,char*t,size_t n,const char*unit){const ha_entity_t*e=entity(slot);snprintf(t,n,"%s%s",e&&e->available?e->state:"--",unit?unit:e?e->unit:"");}
static __attribute__((unused)) void mini_car(void){box(s_pane,144,123,178,40,0xC4D9E5,17);box(s_pane,174,99,112,40,0x698CA1,20);box(s_pane,157,157,35,16,0x324352,8);box(s_pane,279,157,35,16,0x324352,8);box(s_pane,158,132,27,7,BLUE,3);box(s_pane,283,132,27,7,BLUE,3);}
static void dashboard(void){
 int online=0,lights=0,on=0;for(int i=0;i<s_data->ha_entity_count;i++){const ha_entity_t*e=entity(i);online+=e->available;if(!strcmp(e->domain,"light")){lights++;on+=!strcmp(e->state,"on");}}
 int percent=s_data->ha_entity_count?online*100/s_data->ha_entity_count:0;outer(connected()?percent:0,lights?on*100/lights:0,90);
 art(&ha_art_wifi,110,104);label(s_pane,"在线率",68,139,116,MUTED);char t[100];if(connected())snprintf(t,sizeof(t),"%d%%",percent);else strcpy(t,"离线");lv_obj_t*l=label(s_pane,t,68,166,116,TEXT);lv_obj_set_style_text_font(l,&lv_font_montserrat_32,0);
 time_t now=time(NULL);struct tm tm;localtime_r(&now,&tm);snprintf(t,sizeof(t),"%02d:%02d",tm.tm_hour,tm.tm_min);s_clock=big(t,111,212,244);lv_obj_set_style_text_font(s_clock,&ui_font_ha_numbers_80,0);
 art(&ha_art_bulb,107,278);label(s_pane,"灯光",68,310,110,MUTED);snprintf(t,sizeof(t),"%d/%d",on,lights);l=label(s_pane,t,68,337,110,TEXT);lv_obj_set_style_text_font(l,&lv_font_montserrat_32,0);
 int pm=role("pm25");art(&ha_art_leaf,350,146);label(s_pane,"空气",322,185,94,MUTED);const ha_entity_t*air=entity(pm);lv_obj_t*q=label(s_pane,air&&air->available?atof(air->state)<=35?"优":atof(air->state)<=75?"良":"偏高":"--",327,211,80,BLUE);lv_obj_set_style_transform_scale(q,430,0);lv_obj_set_style_transform_pivot_x(q,40,0);state_value(pm,t,sizeof(t),"");char pm_text[64];snprintf(pm_text,sizeof(pm_text),"PM2.5 %.40s",t);label(s_pane,pm_text,303,255,116,MUTED);
 int w=domain("weather",0);const ha_entity_t*weather=entity(w);art(&ha_art_weather,190,112);
 state_value(role("temperature"),t,sizeof(t),"°C");char climate_line[100];snprintf(climate_line,sizeof(climate_line),"%.40s  %s",t,weather&&weather->available?!strcmp(weather->state,"rainy")?"下雨":!strcmp(weather->state,"sunny")?"晴天":"多云":"--");label(s_pane,climate_line,160,285,162,TEXT);state_value(role("humidity"),t,sizeof(t),"%");char humidity[70];snprintf(humidity,sizeof(humidity),"湿度 %.40s",t);label(s_pane,humidity,162,313,150,MUTED);
 if(connected()){button(s_pane,"",199,357,70,63,1001,false);art(&ha_art_ha_home,199,357);}
}
static void list(const char*d,const char*title){top(title);int n=count(d);int pages=(n+3)/4;if(pages<1)pages=1;if(s_list_page>=pages)s_list_page=0;
 for(int i=0;i<4;i++){int slot=domain(d,s_list_page*4+i);const ha_entity_t*e=entity(slot);if(!e)continue;int x=91+(i%2)*149,y=109+(i/2)*112;lv_obj_t*b=button(s_pane,"",x,y,135,102,2000+slot,!e->available);label(b,e->label,5,16,125,TEXT);char t[70];if(!e->available)strcpy(t,"不可用");else if(!strcmp(d,"climate"))snprintf(t,sizeof(t),"%s %.1f°",mode_text(e->state),(double)e->temperature);else strcpy(t,!strcmp(e->state,"on")?"已开启":"已关闭");label(b,t,3,53,129,!strcmp(e->state,"on")?BLUE:MUTED);}
 if(n==0)label(s_pane,"暂未添加设备",80,202,306,MUTED);
 button(s_pane,LV_SYMBOL_LEFT,119,343,44,44,110,s_list_page==0);button(s_pane,LV_SYMBOL_RIGHT,303,343,44,44,111,s_list_page>=pages-1);
 char text[30];snprintf(text,sizeof(text),"%d / %d",s_list_page+1,pages);label(s_pane,text,179,353,108,MUTED);
}
static void detail(void){const ha_entity_t*e=entity(s_selected);if(!e)return;char title[80];snprintf(title,sizeof(title),"%s%s",e->label,connected()?"":" · 离线");top(title);bool locked=blocked(e);bool climate=!strcmp(e->domain,"climate"),light=!strcmp(e->domain,"light"),toggle=light||!strcmp(e->domain,"switch");
 if(climate){lv_obj_t*choose=button(s_pane,"",127,45,228,44,121,count(e->domain)<2);lv_obj_set_style_bg_opa(choose,LV_OPA_TRANSP,0);lv_obj_set_style_border_width(choose,0,0);}
 int value=climate?(int)((e->temperature-e->min_temp)*100/fmaxf(e->max_temp-e->min_temp,1)):light?(int)(fmaxf(e->brightness,0)*100/255):(int)fmaxf(e->percentage,0);
 if(toggle&&!e->brightness_supported)value=!strcmp(e->state,"on")?100:0;
 arc(103,92,260,135,405,e->available?value:0,BLUE,17);if(light)art(&ha_art_bulb,218,132);else if(climate)art(&ha_art_snow,218,132);else icon(LV_SYMBOL_LOOP,183,132,100,BLUE);
 char t[60];if(!e->available)strcpy(t,"--");else if(climate)snprintf(t,sizeof(t),"%.1f°",(double)e->temperature);else if(toggle&&!e->brightness_supported)strcpy(t,!strcmp(e->state,"on")?"已开启":"已关闭");else if(value<0)strcpy(t,"--");else snprintf(t,sizeof(t),"%d%%",value);
 if(climate||(light&&e->brightness_supported)||!toggle)big(t,126,185,214);else label(s_pane,t,143,206,180,TEXT);
 label(s_pane,climate?mode_text(e->state):toggle?e->brightness_supported?"亮度":"开关控制":!strcmp(e->state,"off")?"已关闭":"风速",130,266,206,MUTED);
 button(s_pane,climate?"-":LV_SYMBOL_LEFT,64,226,48,48,climate?201:120,climate?locked||!e->temperature_available||e->temperature-e->temp_step<e->min_temp:count(e->domain)<2);button(s_pane,climate?"+":LV_SYMBOL_RIGHT,354,226,48,48,climate?202:121,climate?locked||!e->temperature_available||e->temperature+e->temp_step>e->max_temp:count(e->domain)<2);
 if(climate){bool has_off=false;for(int i=0;i<e->mode_count;i++)has_off|=!strcmp(e->modes[i],"off");button(s_pane,LV_SYMBOL_POWER,209,295,48,48,200,locked||!has_off);
  const char*m[]={"cool","heat","fan_only","dry"};const lv_image_dsc_t*icons[]={&ha_art_mode_cool,&ha_art_mode_heat,&ha_art_mode_fan,&ha_art_mode_dry};
  box(s_pane,107,352,252,54,TRACK,27);
  for(int i=0;i<4;i++){int index=-1;for(int j=0;j<e->mode_count;j++)if(!strcmp(e->modes[j],m[i]))index=j;button(s_pane,"",114+i*62,354,48,48,300+(index<0?HA_MODE_MAX:index),locked||index<0);art(icons[i],120+i*62,363);}
  button(s_pane,"模式",174,405,118,30,203,locked||!e->mode_count);
 }
 else{button(s_pane,LV_SYMBOL_POWER,200,314,66,66,200,locked);bool pct=light?e->brightness_supported:e->percentage_supported;if(pct){button(s_pane,"-",123,322,50,50,204,locked);button(s_pane,"+",293,322,50,50,205,locked);}}
 if(s_select_mode&&climate){box(s_pane,70,309,326,125,0,0);for(int i=0;i<e->mode_count;i++)button(s_pane,mode_text(e->modes[i]),81+(i%4)*77,312+(i/4)*49,72,44,300+i,locked);}
}
static void environment(void){top("室内环境");const char*r[]={"temperature","humidity","pm25"};const char*caption[]={"客厅温度","客厅湿度","空气 PM2.5"};const char*units[]={"°C","%",""};for(int i=0;i<3;i++){int y=113+i*82;button(s_pane,i==1?LV_SYMBOL_TINT:i==2?LV_SYMBOL_REFRESH:LV_SYMBOL_CHARGE,87,y,54,54,1003,false);char t[70];state_value(role(r[i]),t,sizeof(t),units[i]);label(s_pane,caption[i],160,y,208,MUTED);lv_obj_t*l=label(s_pane,t,160,y+25,208,TEXT);lv_obj_set_style_text_font(l,&lv_font_montserrat_32,0);}nav();}
static void vacuum(void){top("扫地机器人");int slot=domain("vacuum",0);const ha_entity_t*e=entity(slot);if(!e){label(s_pane,"暂未添加设备",90,206,286,MUTED);nav();return;}int bat=role("vacuum_battery");char t[80];state_value(bat,t,sizeof(t),"%");int v=entity(bat)&&entity(bat)->available?atoi(entity(bat)->state):0;arc(108,90,250,135,405,v,BLUE,17);icon(LV_SYMBOL_LOOP,182,130,102,BLUE);big(t,134,190,198);const char*state=!e->available?"不可用":!strcmp(e->state,"docked")?"充电座待机":!strcmp(e->state,"cleaning")?"清扫中":!strcmp(e->state,"paused")?"已暂停":!strcmp(e->state,"returning")?"返回充电座":!strcmp(e->state,"error")?"故障":"空闲";label(s_pane,state,110,266,246,MUTED);bool b=blocked(e);s_selected=slot;button(s_pane,LV_SYMBOL_PLAY,104,315,54,54,400,b||!(e->vacuum_actions&1));button(s_pane,LV_SYMBOL_PAUSE,172,315,54,54,401,b||!(e->vacuum_actions&2));button(s_pane,LV_SYMBOL_STOP,240,315,54,54,402,b||!(e->vacuum_actions&4));button(s_pane,LV_SYMBOL_HOME,308,315,54,54,403,b||!(e->vacuum_actions&8));label(s_pane,"开始 / 暂停 / 停止 / 回充",79,380,308,MUTED);}
static void vehicle(void){int bat=role("vehicle_battery");char t[100];state_value(bat,t,sizeof(t),"%");int v=entity(bat)&&entity(bat)->available?atoi(entity(bat)->state):0;outer(v,0,80);art(&ha_art_car,125,94);art(&ha_art_battery,115,204);lv_obj_t*power=big(t,185,195,206);lv_obj_set_style_text_font(power,&ui_font_ha_numbers_80,0);state_value(role("vehicle_range"),t,sizeof(t)," km");label(s_pane,t,130,268,206,TEXT);const ha_entity_t*lock=entity(role("vehicle_lock")),*charging=entity(role("vehicle_charging"));label(s_pane,lock&&lock->available?!strcmp(lock->state,"on")?"已锁车":"未锁车":"锁车 --",70,318,110,MUTED);label(s_pane,charging&&charging->available?!strcmp(charging->state,"Charging")?"充电中":"未充电":"充电 --",180,318,110,MUTED);state_value(role("vehicle_temperature"),t,sizeof(t),"°C");label(s_pane,t,290,318,108,MUTED);const ha_entity_t*status=entity(role("vehicle_status"));label(s_pane,status&&!strcmp(status->state,"offline")?"车辆离线 · 最近数据":"车辆状态 · 只读",92,361,282,BLUE);}
static void nas(void){top("NAS 状态");art(&ha_art_nas,207,97);const char*r[]={"nas_cpu","nas_memory","nas_temperature"},*c[]={"CPU","内存","温度"},*u[]={"%","%","°C"};for(int i=0;i<3;i++){char t[80];state_value(role(r[i]),t,sizeof(t),u[i]);label(s_pane,c[i],94,169+i*62,110,MUTED);label(s_pane,t,224,169+i*62,145,TEXT);}nav();}
static void extras(void){top("其他设备");int slots[HA_ENTITY_MAX],n=0;for(int i=0;i<s_data->ha_entity_count;i++){const ha_entity_t*e=entity(i);if(!strcmp(e->domain,"fan")||!strcmp(e->domain,"switch"))slots[n++]=i;}int pages=(n+3)/4;if(pages<1)pages=1;if(s_list_page>=pages)s_list_page=0;for(int i=0;i<4;i++){int j=s_list_page*4+i;if(j>=n)continue;const ha_entity_t*e=entity(slots[j]);lv_obj_t*b=button(s_pane,"",91+i%2*149,112+i/2*112,135,102,2000+slots[j],!e->available);label(b,e->label,5,19,125,TEXT);label(b,!strcmp(e->state,"on")?"已开启":"已关闭",5,55,125,MUTED);}if(!n)label(s_pane,"暂未添加设备",80,202,306,MUTED);nav();}
static void build(void){if(!s_data||!s_pane)return;s_dirty=false;lv_obj_clean(s_pane);s_clock=NULL;s_footer=NULL;
 if(s_selected<0&&(s_page==1||s_page==2))s_selected=domain(s_page==1?"light":"climate",0);
 if(s_selected>=0&&s_page!=4)detail();else switch(s_page){case 0:dashboard();break;case 1:list("light","灯光控制");break;case 2:list("climate","空调控制");break;case 3:environment();break;case 4:vacuum();break;case 5:vehicle();break;case 6:nas();break;default:extras();break;}
 for(int i=0;i<8;i++)box(s_pane,179+i*14,438,i==s_page?10:6,6,i==s_page?BLUE:TRACK,3);
 s_footer=label(s_pane,"",103,413,260,MUTED);lv_obj_set_style_transform_scale(s_footer,205,0);lv_obj_set_style_transform_pivot_x(s_footer,130,0);lv_obj_set_style_transform_pivot_y(s_footer,0,0);
}
lv_obj_t*ha_ui_create(bool(*allowed)(void)){s_touch_allowed=allowed;s_large_font=ui_font_digits_64;s_large_font.fallback=&ui_font_ha_symbols_64;s_screen=lv_obj_create(NULL);lv_obj_remove_flag(s_screen,LV_OBJ_FLAG_SCROLLABLE);lv_obj_set_style_bg_color(s_screen,lv_color_hex(0),0);s_pane=box(s_screen,0,0,466,466,0,0);return s_screen;}
void ha_ui_back(void){if(s_select_mode)s_select_mode=false;else {s_selected=-1;s_page=0;}build();}
void ha_ui_page(int delta){s_page=(s_page+8+delta)%8;s_selected=-1;s_select_mode=false;s_list_page=0;build();}
void ha_ui_update(const codex_snapshot_t*s){if(s->ha_revision!=s_revision){s_selected=-1;s_select_mode=false;s_page=0;s_pending=0;s_revision=s->ha_revision;}
 const unsigned char*p=(const unsigned char*)s->ha_entities;uint32_t h=2166136261U;for(size_t i=0;i<sizeof(s->ha_entities);i++)h=(h^p[i])*16777619U;h^=s->ha_connected;h^=s->ha_result_seq*17U;s_dirty|=h!=s_hash;s_hash=h;s_data=s;if(s_pending&&s->ha_result_seq!=s_pending_seq){s_pending=0;s_dirty=true;}ha_ui_tick();}
void ha_ui_tick(void){if(!s_data)return;if(s_pending&&lv_tick_elaps(s_pending)>30000){s_pending=0;s_dirty=true;}
 bool pressed=false;for(lv_indev_t*i=lv_indev_get_next(NULL);i;i=lv_indev_get_next(i))if(lv_indev_get_state(i)==LV_INDEV_STATE_PRESSED)pressed=true;if(s_dirty&&!pressed)build();
 if(s_clock){time_t now=time(NULL);struct tm tm;localtime_r(&now,&tm);char t[10];snprintf(t,sizeof(t),"%02d:%02d",tm.tm_hour,tm.tm_min);lv_label_set_text(s_clock,t);}
 if(s_footer)lv_label_set_text(s_footer,s_selected>=0&&s_page!=4?"":s_pending&&s_page!=0?"正在发送…":connected()?"":"离线 · 暂停控制");
}
bool ha_ui_detail_active(void){return s_selected>=0&&s_page!=4;}
