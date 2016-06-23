// app.js
// create our angular app and inject ngAnimate and ui-router 
// =============================================================================
angular.module('formApp', ['ngAnimate', 'ui.router'])

// configuring our routes 
// =============================================================================
.config(function($stateProvider, $urlRouterProvider) {
    
    $stateProvider
        .state('form', {
            url: '/form',
            templateUrl: 'html/form.html',
            controller: 'formController'
        })
        .state('form.welcome', {
            url: '/welcome',
            templateUrl: 'html/form-welcome.html'
        })
        .state('form.signup', {
            url: '/signup',
            templateUrl: 'html/form-signup.html'
        })
        .state('form.token', {
            url: '/token',
            templateUrl: 'html/form-token.html'
        })
        .state('form.finish', {
            url: '/finish',
            templateUrl: 'html/form-finish.html'
        });

    $urlRouterProvider.otherwise('/form/welcome');
})

// our controller for the form
// =============================================================================
.controller('formController', function($scope, $http, $window) {
    
    // we will store all of our form data in this object
    $scope.formData = {};
    
    // function to process the form
    $scope.processForm = function() {
        $http.post('index.html', $scope.formData)
    };
    
})
//file read directive for token upload
.directive('onReadFile', function ($parse) {
	return {
		restrict: 'A',
		scope: false,
		link: function(scope, element, attrs) {
            var fn = $parse(attrs.onReadFile);
            
			element.on('change', function(onChangeEvent) {
				var reader = new FileReader();
                
				reader.onload = function(onLoadEvent) {
					scope.$apply(function() {
						fn(scope, {$fileContent:onLoadEvent.target.result});
					});
				};

				reader.readAsText((onChangeEvent.srcElement || onChangeEvent.target).files[0]);
			});
		}
	};
});