
from pprint import pprint


from enocean.protocol.eep import EEP, DataStatus, DataValue, DataEnum, ProfileData, Profile, Profiles


if __name__ == "__main__":


    e = EEP()
    print(e.init_ok)
    # pprint(e.telegrams.keys())
    for rorg, v1 in e.telegrams.items():
        # print(rorg, v1)
        for func, v2 in v1.items():
            # print(rorg, func)
            for profile, definition in v2.items():
                print(hex(rorg), hex(func), hex(profile))
                # p = Profile(definition)
                # print(p)
                # print(definition)
                # datas = definition.findall("data")
                # for d in datas:
                #     # print(type(d), d.tag)
                #     d2 = ProfileData(d)
                #     print(d2)
                    # for x in d.iter():
                    #     try:
                    #         if x.tag == "status":
                    #             # print("\t\t", DataStatus(x))
                    #             if not DataStatus(x).shortcut:
                    #                 print("\t\t", DataStatus(x))
                    #                 raise ValueError("lala")
                    #         elif x.tag =="value":
                    #             # print(DataValue(x))
                    #             if not DataValue(x).shortcut:
                    #                 print(DataValue(x))
                    #                 print(DataValue(x).shortcut)
                    #                 raise ValueError("lala")
                    #         elif x.tag == "enum":
                    #             # print(DataEnum(x))
                    #             if not DataEnum(x).shortcut:
                    #                 print(DataEnum(x))
                    #                 raise ValueError("lala")
                    #     except Exception as e:
                    #         print(x)
                    #         raise e
                    # if v := d.find("value"):
                    #     data = DataValue(v)
                    #     print(data)