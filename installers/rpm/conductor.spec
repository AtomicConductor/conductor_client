%define __spec_install_post %{nil}
%define debug_package %{nil}
%define __os_install_post %{_dbpath}/brp-compress

Summary: Conductor Client
Name: conductor
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
Version: %{_version}
Release: 0.%{_dist}
<<<<<<< HEAD
=======
Version: 1
Release: 0
>>>>>>> af70b55... RPM package
=======
Version: %{_major_version}
Release: %{_minor_version}
Patch: %{_patch_version}
>>>>>>> 5ca5f82... version info
=======
Version: %{_version}
Release: 0
>>>>>>> cfa5cb5... release versions
=======
>>>>>>> e29ba55... dist version in rpms
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
<<<<<<< HEAD
<<<<<<< HEAD
#rm -rf %{buildroot}
=======
rm -rf %{buildroot}
>>>>>>> af70b55... RPM package
=======
#rm -rf %{buildroot}
>>>>>>> e29ba55... dist version in rpms

%files
%defattr(-,root,root,-)
/*

%changelog
