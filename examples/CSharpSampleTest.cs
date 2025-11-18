using NUnit.Framework;
using System.Threading;
using System.IO;

namespace TestProject
{
    [TestFixture]
    public class SampleTests
    {
        [SetUp]
        public void Setup()
        {
            // Setup code
        }

        [Test]
        public void TestAddition()
        {
            int result = 2 + 2;
            Assert.AreEqual(4, result);
        }

        [Test]
        public void TestWithSleep()
        {
            // BAD: Time-based wait
            Thread.Sleep(1000);
            Assert.IsTrue(true);
        }

        [Test]
        public void TestTooManyAssertions()
        {
            // BAD: Too many assertions
            Assert.AreEqual(1, 1);
            Assert.AreEqual(2, 2);
            Assert.AreEqual(3, 3);
            Assert.AreEqual(4, 4);
            Assert.AreEqual(5, 5);
        }

        [Test]
        public void TestNoAssertions()
        {
            // BAD: No assertions
            int x = 2 + 2;
        }

        [Test]
        public void TestWithLogic()
        {
            // BAD: Conditional logic
            int value = 10;
            if (value > 5)
            {
                Assert.IsTrue(value > 5);
            }
        }
    }
}
