
JOB = """


     attribute_group "status" {
         string "info" {
            value "Some info"
        }
     }


     attribute_group "general" {
      reference "source" {
            filter "Image"
        }
          string "title" {
            doc "Set the title that will appear in the Conductor dashboard."
            value ""
        }
        long "project" {
            doc "Set the Conductor project to render into."
            value 0
            preset "- Not set -" "0"

        }

        string "last_project" {
            value "" 
            hidden yes
        }

     }

 



    attribute_group "frames" {
        bool "use_custom_frames" {
            value no
        }

        string "custom_frames" {
            value "2,4-8,10-50x2"
            hidden yes
        }
        frame "chunk_size" {
            value 5
            numeric_range_min yes 1
        }
        bool "use_scout_frames" {
            value no
        }
        string "scout_frames" {
            value "2,4-8,10-50x2"
            hidden yes
        }
        string "frames_info" {
            value "- Please refresh -"
        }

    }

    



    attribute_group "machines" {

        bool "preemptible" {
            doc "Preemptible instances are less expensive, but may be interrupted."
            value no
        }

        long "instance_type" {
            doc "Choose your ideal machine spec."
            value 0
            preset "- Not set -" "0"

        }

        long "retries" {
            value 3
            numeric_range_min yes 1
        }
    }

    


    """
 # attribute_group "Image" {
 #        reference "source" {
 #            filter "Image"
 #        }
 #    }

        #  reference "source" {
        #     filter "Image"
        # }