import pandas as pd


class Strategy:
    name = "Base"
    
    def __init__(self, period: int, expiry_time: int):
        print("Creating strategy: ", self.name)
        self.period = period
        self.expiry_time = expiry_time
        
    def set_hyperparameters(self, options: dict):
        if options is not None:
            for key in options.keys():
                self.__setattr__(key, options[key])
    
    def update_hyperparameter(self, parameter_name: str, parameter_value: any):
        try:
            self.__getattribute__(parameter_name)
            self.__setattr__(parameter_name, parameter_value)
        except:
            return
        
            
    def process_data(self):
        # 0 = no action; 1 = call, 2 = put
        return 0