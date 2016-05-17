%define __spec_install_post %{nil}
%define debug_package %{nil}
%define __os_install_post %{_dbpath}/brp-compress

Summary: Conductor Client
Name: conductor
Version: %{_version}
Release: 0.%{_dist}
License: Proprietary
Group: Applications/Multimedia
URL: https://www.conductorio.com
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root
AutoReqProv: no

%description
%{summary}

%prep
# Empty section.

%build
# Empty section.

%install
#cp -a * %{buildroot}

%clean
#rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
/*

%changelog