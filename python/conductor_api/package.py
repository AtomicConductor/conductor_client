import conductor
import conductor.lib.api_client

class Product(object):
    '''A Product is a top-level software product (versionless, etc...)
    
    Examples of Product's are Maya, Houdini, Golaem, etc...
    
    Product's contain Packages which are the specific versions or releases
    of a Product
    '''    
    
    _data = None
    _products = None
    
    def __init__(self):
        self.name = None
        self.packages = []
        
    
    @classmethod
    def _get_package_json(cls):
        
        if cls._data is None:

            cls._data = conductor.lib.api_client.request_software_packages()
            
        return cls._data
    

    @classmethod
    def get_products(cls):
        
        if cls._products is None:
            
            data = cls._get_package_json()
            cls._products = {}
            
            for package in data:
                if package['product'] not in cls._products:
                    cls._products[package['product']] = cls()
                
                cls._products[package['product']].packages.append(Package.create_from_json(package))
            
            print len(data)
            print data[0].keys()
                        
        return cls._products

class Package(object):

    def __init__(self):
        
        self._json_data = None
        self.build_id = None
        self.build_version = None
        self.description = None
        self.environment = None
        self.major_version = None
        self.minor_version = None
        self.package = None
        self.package_id = None
        self.path = None
        self.plugin_host_product = None
        self.plugin_host_version = None
        self.plugin_hosts = None
        self.plugins = None
        self.product = None
        self.relative_path = None
        self.release_version = None
        self.time_created = None
        self.time_updated = None
        self.updated_at = None
        self.vendor = None
        
    @classmethod
    def create_from_json(cls, data):
        
        new_package = cls()
        new_package._json_data = data
        
        return new_package

    @classmethod
    def find(cls):
        pass


print Product.get_products()['maya-io'].packages






















    