#[cfg(test)]
mod tests {
    use std::thread;
    use std::time::Duration;
    use std::fs::File;

    #[test]
    fn test_addition() {
        assert_eq!(2 + 2, 4);
    }

    #[test]
    fn test_with_sleep() {
        // BAD: Time-based wait
        thread::sleep(Duration::from_secs(1));
        assert!(true);
    }

    #[test]
    fn test_too_many_assertions() {
        // BAD: Too many assertions
        assert_eq!(1, 1);
        assert_eq!(2, 2);
        assert_eq!(3, 3);
        assert_eq!(4, 4);
        assert_eq!(5, 5);
    }

    #[test]
    fn test_no_assertions() {
        // BAD: No assertions
        let x = 2 + 2;
    }

    #[test]
    fn test_with_logic() {
        // BAD: Conditional logic
        let value = 10;
        if value > 5 {
            assert!(value > 5);
        }
    }
}
