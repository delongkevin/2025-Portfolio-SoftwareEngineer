gen_absent_present = ["Absent", "Present"]

countries = {"00":"World","02":"United States of America","04":"Canada","0A":"China Mainland",
"0E":"Mexico","12":"Bahrain","61":"Iraq","68":"Jordan", "6C":"Kuwait", "70":"Lebanon", "95":"Oman", "A0":"Qatar", "A5":"Saudi Arabia", "CC":"United Arab Emirates", "D7":"Yemen"}

drive_type_variant = ["FWD", "RWD", "Single Speed AWD", 
                     "2 Speed 4WD", "2 Speed 4WD with ELSD"]

gear_box_type = ["Not Valid", "MTX", "MTA", "DDCT", "ATX", "CVT"]

pam_tuning_set = ["None", "Base", "Rebel", "TRX", "Tungsten", "Big Horn/Lone Star", "REPB/BEV"]

tyre_size_list = []

hybrid_type = ["Not Applicable", "Battery Electric Vehicle (BEV)", 
              "Hybrid Elective Vehicle", "Plugin Hybrid Electric Vehicle", "48V Belt Start Generator (BSG)", "12V Belt Start Generator (BSG)", "Range Electric Paradigm Breaker (REPB)"]

vehicle_line_config = {"00":"Invalid", "33":"343 (33 Hex)", "34":"327FL (34 Hex)", "35": "226 (35 Hex)", "50": "PF (50 Hex)", "51" : "KL/K4  (51 Hex)","52" : "UF (52 Hex)","53" : "UT (53 Hex)","54" : "334 (54 Hex)","55" : "520 (55 Hex)","56" : "551 /M1 (56 Hex)","57" : "338 (57 Hex)","58" : "521 (58 Hex)","59" : "636 VM (59 Hex)","5A" : "356 (5A Hex)","5B" : "952 (5B Hex)","5C" : "341 (5C Hex)","5D" : "552/MP (5D Hex)","5E" : "949 (5E Hex)","5F" : "523 (5F Hex)","60" : "358 (60 Hex)","61" : "359 (61 Hex)","62" : "553/M4 (62 Hex)","63" : "556/M6 (63 Hex)","64" : "K8 (64 Hex)","65" : "WL (65 Hex)","66" : "281 (66 Hex)","67" : "363 (67 Hex)","68" : "WS (68 Hex)","69" : "332 (69 Hex)","6A" : "560 (6A Hex)","7C" : "DT (7C hex)", "82" : "HDCC (82 Hex)"}

steering_ratio_rack_pinion_type = ["Type 1", "Type 2", "Type 3"]

pam_configuration = ["Rear", "Front And Rear"]

wheelbase = ["Type_1 (140.5 inch/Quad Cab 6'4 Box)", "Type_2 (144.5 inch/Crew Cab 5'7 Box)", 
"Type_3 (153.5 inch/Crew Cab 6'4 Box)"]

radio_display_type = ["Absent",'7" 1280x768', '8.4" 1024x768','10.1" 1920x1200', 
                      '10.1" 1200x1920', '10.25" 1920x720', '12" 1920x1200',
                      '12" 1200x1920', '12.3" 1920x720', '14.5" 1024x1920']

autonomy_level = ["None/Level 1", "Level 2", "Level 2 Plus"]

body_types_list = ["Absent", "Type 1 - D2", "Type 2 - DD", "Type 3 - DF", "Type 4 - DJ",
                   "Type 5 - DP", "Type 6 - DX", "Type 7 - DT"]

model_year_list = []

proxy_length_list = []

proxytype = [proxy_length_list, countries, drive_type_variant, gear_box_type, pam_tuning_set, tyre_size_list, vehicle_line_config, gen_absent_present, gen_absent_present, hybrid_type, steering_ratio_rack_pinion_type, pam_configuration, wheelbase, radio_display_type, autonomy_level, gen_absent_present, gen_absent_present,model_year_list, gen_absent_present,gen_absent_present,gen_absent_present, body_types_list, gen_absent_present,gen_absent_present, gen_absent_present,gen_absent_present,gen_absent_present,gen_absent_present,gen_absent_present, gen_absent_present,gen_absent_present,gen_absent_present,gen_absent_present, gen_absent_present]

category_list = ["Proxy Length", "Country_Code", "Drive_Type_Variant", "Gear_Box_Type", "PAM_Tuning_Set", "Tyre_Size", "Vehicle_Line_Config", "Can Node 63", "Can Node 67", "Hybrid_Type", "Steering_Ratio_Rack_Pinion_Type" , "PAM_Configuration", "Wheelbase", "Radio_Display_Type", "Autonomy_Level", "Can Node 95", "Surround_View_Cam", "Model_Year", "Trailer_Reverse_Steering_Presence", "Trailer_Hitch_Assist_Presence" ,"Dual_Rear_Wheels_Present", "Body_Types", "Can Node 27", "SRT", "Auxiliary_Trailer_Camera", "Trailer_Surround_Presence", "Can Node 41", "Forward_Facing_Camera", "Trailer_Reverse_Guidance_Presence", "Box_Delete", "Digital_Chmsl_Camera_Prsnt", "CVPAM_Prsnt", "Can Node 24"]

def country_find(line, bytes):
  country_code = line[212:214]
  bytes.append(country_code)
  return bytes
  
def drive_type_variant_find(line, bytes):
  drive_type_variant = line[180]
  drive_bin = bin(int(drive_type_variant,16))[2:].zfill(4)
  bytes.append(int(drive_bin[-2]))
  return bytes

def gear_box_type_find(line, bytes):
  gear_box_type = line[201]
  gear_bin = bin(int(gear_box_type, 16))[2:].zfill(4)
  bytes.append(int(gear_bin[-3::],2))
  return bytes

def pam_tuning_set_find(line, bytes):
  pam_tuning_set = line[207]
  pam_bin = bin(int(pam_tuning_set, 16))[2:].zfill(4)
  bytes.append(int(pam_bin[-3::], 2))
  return bytes
  
def tyre_size_find(line, bytes):
  tyre_size = line[126:130]
  tyre_size_list.append(str(int(tyre_size,16)))
  bytes.append(0)
  return bytes

def vehicle_line_config_find(line, bytes):
  vehicle_line_config = line[208:210]
  bytes.append(vehicle_line_config)
  return bytes

def can_node_63_find(line, bytes):
  can_node_63 = line[64]
  can_bin = bin(int(can_node_63,16))[2:].zfill(4)
  bytes.append(int(can_bin[0]))
  return bytes

def can_node_67_find(line, bytes):
  can_node_67 = line[67]
  can_bin = bin(int(can_node_67,16))[2:].zfill(4)
  bytes.append(int(can_bin[0]))
  return bytes

def hybrid_type_find(line, bytes):
  hybrid_type = line[281] #02 is 0x1
  bytes.append(int(hybrid_type))
  return bytes

def steering_ratio_rack_pinion_type_find(line, bytes):
  steering_ratio_rack_pinion_type = line[175]
  steer_bin = bin(int(steering_ratio_rack_pinion_type,16))[2:].zfill(2)
  bytes.append(int(steer_bin[-2::],2))
  return bytes

def pam_configuration_find(line, bytes):
  pam_config = line[234]
  pam_bin = bin(int(pam_config,16))[2:]
  bytes.append(int(pam_bin[-2::],2))
  return bytes

def wheelbase_find(line, bytes):
  wheelbase = line[140]
  bytes.append(int(wheelbase))
  return bytes

def radio_display_type_find(line, bytes):
  radio_display_type = line[369]
  bytes.append(int(radio_display_type))
  return bytes

def autonomy_level_find(line, bytes):
  autonomy_level = line[353]
  autonomy_bin = bin(int(autonomy_level,16))[2:].zfill(4)
  bytes.append(int(autonomy_bin[1],2))
  return bytes

def can_node_95_find(line, bytes):
  can_node_95 = line[72]
  can_bin = bin(int(can_node_95,16))[2:]
  bytes.append(int(can_bin[0]))
  return bytes

def surround_view_cam_find(line, bytes):
  surround_view_cam = line[353]
  surround_bin = bin(int(surround_view_cam,16))[2:]
  bytes.append(int(surround_bin[-1],2))
  return bytes

def model_year_find(line, bytes):
  model_year = line[249]
  model_year_list.append(model_year)
  bytes.append(0)
  return bytes

def trailer_reverse_steering_presence_find(line, bytes):
  trailer_reverse_steering_presence = line[420]
  trailer_bin = bin(int(trailer_reverse_steering_presence,16))[2:].zfill(4)
  bytes.append(int(trailer_bin[-4],2))
  return bytes

def trailer_hitch_assist_presence_find(line, bytes):
  trailer_hitch_assist_presence = line[425]
  trailer_bin = bin(int(trailer_hitch_assist_presence,16))[2:].zfill(2)
  bytes.append(int(trailer_bin[-2],2))
  return bytes

def dual_rear_wheels_present_find(line, bytes):
  dual_rear_wheels_present = line[453]
  dual_bin = bin(int(dual_rear_wheels_present,16))[2:].zfill(4)
  bytes.append(int(dual_bin[-3],2))
  return bytes

def body_types_find(line, bytes):
  body_types = line[461]
  body_bin = bin(int(body_types,16))[2:].zfill(4)
  bytes.append(int(body_bin[-3:],2))
  return bytes

def can_node_27_find(line, bytes):
  can_node_27 = line[57]
  can_bin = bin(int(can_node_27,16))[2:].zfill(4)
  bytes.append(int(can_bin[-4],2))
  return bytes

def srt_find(line, bytes):
  srt = line[220]
  srt_bin = bin(int(srt,16))[2:].zfill(4)
  bytes.append(int(srt_bin[-4],2))
  return bytes

def auxiliary_trailer_camera_find(line, bytes):
  auxiliary_trailer_cam = line[421]
  trailer_bin = bin(int(auxiliary_trailer_cam,16))[2:].zfill(4)
  bytes.append(int(trailer_bin[-3],2))
  return bytes

def trailer_surround_presence_find(line, bytes):
  trailer_surround_presence = line[420]
  trailer_bin = bin(int(trailer_surround_presence,16))[2:].zfill(4)
  bytes.append(int(trailer_bin[-3],2))
  return bytes

def can_node_41_find(line, bytes):
  can_node_41 = line[61]
  can_bin = bin(int(can_node_41,16))[2:].zfill(4)
  bytes.append(int(can_bin[-2],2))
  return bytes

def forward_facing_camera_find(line, bytes):
  forward_facing_cam = line[353]
  forward_bin = bin(int(forward_facing_cam,16))[2:].zfill(4)
  bytes.append(int(forward_bin[-2],2))
  return bytes

def trailer_reverse_guidance_presence_find(line, bytes):
  trailer_reverse_guidance_presence = line[421]
  trailer_bin = bin(int(trailer_reverse_guidance_presence,16))[2:].zfill(4)
  bytes.append(int(trailer_bin[-4],2))
  return bytes

def box_delete_find(line, bytes):
  box_delete = line[452]
  box_bin = bin(int(box_delete,16))[2:].zfill(4)
  bytes.append(int(box_bin[-1], 2))
  return bytes

def digital_chmsl_camera_prsnt_find(line, bytes):
  digital_chmsl = line[442]
  bin_digital = bin(int(digital_chmsl,16))[2:].zfill(4)
  bytes.append(int(bin_digital[-4],2))
  return bytes

def cvpam_prsnt_find(line, bytes):
  cvpam_presence = line[345]
  cvpam_bin = bin(int(cvpam_presence,16))[2:].zfill(4)
  bytes.append(int(cvpam_bin[-2],2))
  return bytes

def can_node_24_find(line, bytes):
  can_node_24 = line[57]
  can_bin = bin(int(can_node_24,16))[2:].zfill(4)
  bytes.append(int(can_bin[-1],2))
  return bytes

def bytefinder_new():
  with open("proxystring.txt", "r") as file:
    bytes = []
    for line in file:
      function_list = [country_find, drive_type_variant_find, 
                       gear_box_type_find, 
                     pam_tuning_set_find, tyre_size_find, 
                       vehicle_line_config_find, 
                     can_node_63_find, can_node_67_find, 
                       hybrid_type_find, 
                     steering_ratio_rack_pinion_type_find,
                       pam_configuration_find, 
                     wheelbase_find, radio_display_type_find,
                       autonomy_level_find, 
                     can_node_95_find, 
                       surround_view_cam_find, 
                       model_year_find, 
                       trailer_reverse_steering_presence_find, 
                     trailer_hitch_assist_presence_find, 
                     dual_rear_wheels_present_find, 
                       body_types_find,  
                       can_node_27_find, 
                     srt_find, auxiliary_trailer_camera_find, 
                     trailer_surround_presence_find, 
                       can_node_41_find, 
                     forward_facing_camera_find, 
                       trailer_reverse_guidance_presence_find, 
                     box_delete_find, 
                       digital_chmsl_camera_prsnt_find, 
                       cvpam_prsnt_find, 
                     can_node_24_find]
      proxylength = len(line)
      proxy_length_list.append(str(proxylength))
      bytes.append(0)
      for f in function_list:
        try:
          bytes = f(line, bytes)
        except IndexError:
          print("Index Error: Byte not found!")
          bytes.append(0)

    return bytes

def bytefinder():
  with open("proxyparser/proxystring.txt", "r") as file:
    bytes = []
    for line in file:
      proxylength = len(line)
      proxy_length_list.append(str(proxylength))
      bytes.append(0)
      country_code = line[212:214]
      bytes.append(country_code)
      drive_type_variant = line[180]
      drive_bin = bin(int(drive_type_variant,16))[2:].zfill(4)
      bytes.append(int(drive_bin[-2]))
      gear_box_type = line[201]
      bytes.append(int(gear_box_type))
      pam_tuning_set = line[207]
      bytes.append(int(pam_tuning_set))
      tyre_size = line[126:130]
      tyre_size_list.append(str(int(tyre_size,16)))
      bytes.append(0)
      vehicle_line_config = line[208:210]
      bytes.append(vehicle_line_config)
      can_node_63 = line[64]
      can_bin = bin(int(can_node_63,16))[2:].zfill(4)
      bytes.append(int(can_bin[0]))
      can_node_67 = line[67]
      can_bin = bin(int(can_node_67,16))[2:].zfill(4)
      bytes.append(int(can_bin[0]))
      hybrid_type = line[281] #02 is 0x1
      bytes.append(int(hybrid_type))
      steering_ratio_rack_pinion_type = line[175]
      steer_bin = bin(int(steering_ratio_rack_pinion_type,16))[2:].zfill(2)
      bytes.append(int(steer_bin[-2::],2))
      pam_config = line[234]
      pam_bin = bin(int(pam_config,16))[2:]
      bytes.append(int(pam_bin[-2::],2))
      wheelbase = line[140]
      bytes.append(int(wheelbase))
      radio_display_type = line[369]
      bytes.append(int(radio_display_type))
      autonomy_level = line[353]
      autonomy_bin = bin(int(autonomy_level,16))[2:].zfill(4)
      bytes.append(int(autonomy_bin[1],2))
      can_node_95 = line[72]
      can_bin = bin(int(can_node_95,16))[2:]
      bytes.append(int(can_bin[0]))
      surround_view_cam = line[353]
      surround_bin = bin(int(surround_view_cam,16))[2:]
      bytes.append(int(surround_bin[-1],2))
      model_year = line[249]
      model_year_list.append(model_year)
      bytes.append(0)
      trailer_reverse_steering_presence = line[420]
      trailer_bin = bin(int(trailer_reverse_steering_presence,16))[2:].zfill(4)
      bytes.append(int(trailer_bin[-4],2))
      trailer_hitch_assist_presence = line[425]
      trailer_bin = bin(int(trailer_hitch_assist_presence,16))[2:].zfill(2)
      bytes.append(int(trailer_bin[-2],2))
      try:
        dual_rear_wheels_present = line[453]
        dual_bin = bin(int(dual_rear_wheels_present,16))[2:].zfill(4)
        bytes.append(int(dual_bin[-3],2))
      except (IndexError):
        bytes.append(0)
      try:
        body_types = line[461]
        body_bin = bin(int(body_types,16))[2:].zfill(4)
        bytes.append(int(body_bin[-3:],2))
      except (IndexError):
        print("Body Types not found")
        bytes.append(0)
      can_node_27 = line[57]
      can_bin = bin(int(can_node_27,16))[2:].zfill(4)
      bytes.append(int(can_bin[-4],2))
      srt = line[220]
      srt_bin = bin(int(srt,16))[2:].zfill(4)
      bytes.append(int(srt_bin[-4],2))
      auxiliary_trailer_cam = line[421]
      trailer_bin = bin(int(auxiliary_trailer_cam,16))[2:].zfill(4)
      bytes.append(int(trailer_bin[-3],2))
      trailer_surround_presence = line[420]
      trailer_bin = bin(int(trailer_surround_presence,16))[2:].zfill(4)
      bytes.append(int(trailer_bin[-3],2))
      can_node_41 = line[61]
      can_bin = bin(int(can_node_41,16))[2:].zfill(4)
      bytes.append(int(can_bin[-2],2))
      forward_facing_cam = line[353]
      forward_bin = bin(int(forward_facing_cam,16))[2:].zfill(4)
      bytes.append(int(forward_bin[-2],2))
      trailer_reverse_guidance_presence = line[421]
      trailer_bin = bin(int(trailer_reverse_guidance_presence,16))[2:].zfill(4)
      bytes.append(int(trailer_bin[-4],2))
      try:
        box_delete = line[452]
        box_bin = bin(int(box_delete,16))[2:].zfill(4)
        bytes.append(int(box_bin[-1], 2))
      except (IndexError):
        bytes.append(0)
      digital_chmsl = line[442]
      bin_digital = bin(int(digital_chmsl,16))[2:].zfill(4)
      bytes.append(int(bin_digital[-4],2))
      cvpam_presence = line[345]
      cvpam_bin = bin(int(cvpam_presence,16))[2:].zfill(4)
      bytes.append(int(cvpam_bin[-2],2))
      can_node_24 = line[57]
      can_bin = bin(int(can_node_24,16))[2:].zfill(4)
      bytes.append(int(can_bin[-1],2))
    return bytes

def listmaker(bytevalues=[], selections=[]):
  newlist = []
  amount = len(bytevalues)
  for i in range(0,amount):
    selection = selections[i] 
    newlist.append(selection[bytevalues[i]])
  return newlist

def formatter(value, labels):
  final_list = []
  for i in range(0,len(value)):
    final_list.append(labels[i] + " = " + value[i] + '\n')
  return final_list

def text_output(output = "proxyoutput.txt",found_items = []):
  with open(output, 'w') as file:
    for items in found_items:
      file.write(items)
                     
def main():
  bytes = bytefinder_new()
  newlist = listmaker(bytes, proxytype)
  print(newlist)
  final_list = formatter(newlist, category_list)
  text_output(found_items=final_list)
  #text_output(found_items=newlist)
  pass

if __name__ == '__main__':
  main()
